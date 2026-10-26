# Finalsite contacts: incremental pull design

Refs #4715.

## Problem

`build_finalsite_asset` calls `finalsite.list(path="contacts")`, which walks the
cursor to the end and writes every record as one non-partitioned GCS Avro
object. Every tick is a full snapshot replace. The API caps `count` at 25
records per page and pagination is sequential cursor-only, so kippnewark (~25k
contacts) takes roughly 20 minutes and carries `MAX_RUNTIME_SECONDS_TAG: 3600`
purely to survive its own length. All four districts share the `finalsite_api`
pool at limit 1 (#4408), so the window is the sum across districts, not the max.

The real cost is not compute. It is that freshness is capped at the pull
cadence, and at full-snapshot prices a frequent cadence is unaffordable.

## What the live API actually does

Probed against kippmiami and kippnewark on 2026-08-10 with throwaway harnesses
over the production `FinalsiteResource`. Aggregates only; no student values left
the local checkout.

| Question                                              | Answer                                                                                                                                                                                                       |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Is `since` enforced server-side?                      | Yes. `since=2999-01-01` returns 0 records. A malformed value returns HTTP 400 (`invalid since: must be in YYYY-MM-DD format`), so a bad watermark fails loudly instead of silently degrading to a full pull. |
| Date or timestamp grain?                              | Date. A timestamp is accepted (HTTP 200) but truncated to the day. For day D, `D` / `DT00:00:00Z` / `DT23:59:59Z` returned 1033 / 1033 / 1034 while `D+1` returned 991.                                      |
| Inclusive?                                            | Consistent with on-or-after. Not directly testable without a change timestamp on the payload, and moot once a safety day is subtracted.                                                                      |
| Does `since_includes_expanded=true` widen the result? | No measurable effect. At `since=-1d` on kippmiami the id sets with the flag on and off are identical (1033 each, delta 0).                                                                                   |
| `count` cap                                           | 25 confirmed. Requests for 100 and 500 both returned 25.                                                                                                                                                     |

### Volume, and the over-broadness that shapes the design

`since=today`, measured 2026-08-10:

|                                   | kippmiami  | kippnewark   |
| --------------------------------- | ---------- | ------------ |
| total contacts                    | 7,688      | 25,052       |
| returned by `since=today`         | 990 (13%)  | 2,013 (8%)   |
| pages: incremental vs full        | 40 vs ~308 | 81 vs ~1,002 |
| request reduction                 | ~8x        | ~12x         |
| identical to landed snapshot      | 984 (99%)  | 1,889 (94%)  |
| genuinely changed                 | 6          | 122          |
| new contacts absent from snapshot | 0          | 2            |

Roughly 1,000 (kippmiami) and 2,000 (kippnewark) contacts are touched
server-side each day without any field we land actually moving. Nightly billing
recomputation is the likely source. Tightening the window does not help: on
kippmiami `since=today` and `since=today-1` returned 990 and 1,033 records and
found the **same 6 changes**.

Two consequences:

- The request win is ~8-12x, not the order of magnitude #4715 implies. Still
  enough to make an intraday cadence affordable and to retire kippnewark's
  runtime override.
- The safety day is nearly free (43 extra records, 2 extra pages on kippmiami),
  so take it unconditionally.

Caveat on the diff: `custom_attributes` / `id_attributes` / `track_attributes`
**values** and the billing/financial amounts were excluded, because the landed
Avro shape (`boolean_value` / `string_value` / `array_string_value`) does not
line up with raw API json without a mapping layer. `custom_attributes` was
compared on count only. The changed counts are a floor; the identical
percentages are an upper bound on waste.

## The freshness problem is partly a scheduling bug

Tracing every NJ consumer of `stg_finalsite__contacts` to its schedule:

| NJ destination                      | model                                  | runs at (ET) | contacts age                                |
| ----------------------------------- | -------------------------------------- | ------------ | ------------------------------------------- |
| Google Directory user create/update | `rpt_google_directory__users_import`   | 01:00        | ~21 h, yesterday's pull                     |
| DeansList family contacts           | `rpt_deanslist__family_contacts`       | 01:25        | ~21.4 h, yesterday's pull                   |
| ParentSquare emergency contacts     | `rpt_parentsquare__emergency_contacts` | 18:00        | ~14 h (kippnewark's schedule ships STOPPED) |
| FRESH Dashboard (Tableau)           | `rpt_tableau__fresh_*`                 | 05:00        | ~1 h, correctly sequenced                   |
| Finalsite contacts pull             | —                                      | 04:00        | —                                           |

Three of four NJ consumers run **before** the pull that feeds them. A student
entered in Finalsite Monday morning is pulled Tuesday 04:00 and gets a Google
account Wednesday 01:00 — about 45 hours, of which ~21 are pure mis-ordering.

Moving the pull earlier is unsafe today: four districts serializing full
snapshots through a limit-1 pool takes up to ~46 minutes, so a 00:30 start
finishes ~01:16 and misses the 01:00 sync outright. The incremental change is
what makes the correct ordering fit.

kippmiami additionally has a stakeholder commitment documented in its CLAUDE.md:
a student entered in Finalsite by 12:00 ET is usable in Focus by 14:00 ET, via a
12:45 SFTP delivery that is a plain cron with a time budget, not a dependency.

## Decisions

| Decision                  | Choice                                                                                                                                        |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Storage shape             | Option 2a: Hive-partitioned Avro accumulate by pull date, plus dedupe in staging. Keeps the Avro asset factory and `check_avro_schema_valid`. |
| Watermark                 | The partition key itself. No stored cursor.                                                                                                   |
| Safety day                | Always. `since = partition_date - 1`.                                                                                                         |
| `since_includes_expanded` | Not adopted. Measured no-op, and it was never sent today — all four code locations only ever pass `includes`.                                 |
| Full refresh              | None. Hard deletes are accepted as a known limitation, revisited only if they become a problem.                                               |
| Dedupe location           | `stg_finalsite__contacts`.                                                                                                                    |
| Relationships             | `stg_finalsite__contacts` carries the `relationships` array; `stg_finalsite__contact_relationships` refs it instead of the source.            |
| Cadence                   | 00:15 and 12:00 ET, all four districts. No 04:00.                                                                                             |

## Design

### 1. Ingestion

`build_finalsite_asset` gains a `partitions_def` and derives `since` from the
partition key. The asset key stays `[{code_location}, finalsite, contacts]`.

```python
@asset(
    key=key,
    io_manager_key="io_manager_gcs_avro",
    partitions_def=DailyPartitionsDefinition(start_date=CUTOVER_DATE),
    check_specs=[build_check_spec_avro_schema_valid(key)],
    group_name="finalsite",
    pool="finalsite_api",
    kinds={"python"},
)
def _asset(context: AssetExecutionContext, finalsite: FinalsiteResource):
    partition_date = date.fromisoformat(context.partition_key)
    since = partition_date - timedelta(days=1)

    data = finalsite.list(
        path=asset_name,
        params={**(params or {}), "since": since.isoformat()},
    )
```

Properties:

- The watermark is the partition key. A missed day is a visibly missing
  partition, backfillable with normal partition tooling. No cursor to corrupt.
- Because the safety day makes each pull a superset of any earlier pull on the
  same date, the 12:00 run can overwrite the 00:15 run's partition safely.
- A failed run writes no partition, so nothing advances and nothing is skipped.
- The seed (below) is the one run with `since` omitted, gated behind a run
  config flag so it cannot fire accidentally.

### 2. Storage and the dbt source

The IO manager needs no changes. A `DailyPartitionsDefinition` key parses as
`%Y-%m-%d` and expands to four Hive dimensions:

```text
gs://teamster-<loc>/dagster/<loc>/finalsite/contacts/
  _dagster_partition_fiscal_year=2027/
    _dagster_partition_date=2026-08-10/
      _dagster_partition_hour=00/
        _dagster_partition_minute=00/
          data
```

`hour` and `minute` are constant `00` for a daily partition.

The source gains `hive_partition_uri_prefix`, mirroring `status_report` in the
same file:

```yaml
- name: contacts
  external:
    location: "{{ var('cloud_storage_uri_base') }}/finalsite/contacts/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      hive_partition_uri_prefix:
        "{{ var('cloud_storage_uri_base',
        env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/finalsite/contacts/"
      format: AVRO
      enable_logical_types: true
```

That exposes `_dagster_partition_date` as a pseudo-column for the dedupe to
order on. The `location` glob is unchanged.

### 3. Dedupe and the singleton invariant

`stg_finalsite__contacts` becomes the single dedupe point:

```sql
with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    source as (select * from {{ source("finalsite", "contacts") }}),

    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="source",
                partition_by="id",
                order_by="_dagster_partition_date desc",
            )
        }}
    )

select
    id as finalsite_enrollment_id,
    -- ... existing projection unchanged ...
    relationships,
from deduplicated
```

Rules this follows rather than invents:

- `dbt_utils.deduplicate`, not `QUALIFY` and not dup-masking `SELECT DISTINCT`
  (both banned in `src/dbt/CLAUDE.md`).
- Bare `desc`, never `desc nulls first` — the macro compiles to
  `array_agg(original order by ... limit 1)` and BigQuery rejects explicit
  null-ordering inside an aggregate. Plain `desc` is NULLS LAST.
- `partition_by="id"` matches the downstream join key
  (`finalsite_enrollment_id`).

`relationships` is added to the projection and to the enforced contract:

```yaml
- name: relationships
  data_type:
    array<struct<id string, rel_id string, rel_name string, rel_type string,
    `primary` bool, financial bool, portal_access bool>>
```

`stg_finalsite__contact_relationships` then reads the deduped model:

```sql
select
    finalsite_enrollment_id,
    r.id as relationship_id,
    r.rel_id,
    r.rel_name,
    r.rel_type,
    r.primary as is_primary,
    r.financial as is_financial,
    r.portal_access as has_portal_access,
    household_1_id,
    (
        select logical_or(ca.value.boolean_value),
        from unnest(custom_attributes) as ca
        where ca.field_name = 'is_parent2'
    ) as is_parent2,
from {{ ref("stg_finalsite__contacts") }}
cross join unnest(relationships) as r
```

This also removes a re-derivation: `household_1_id` is already a column on
`stg_finalsite__contacts`, so the relationships model stops recomputing
`households[safe_offset(0)].id`.

Without this change the `cross join unnest` would multiply each contact's
relationships by the number of partitions it appears in.

Downstream of staging nothing changes: the `int_` models, the Focus / DeansList
/ ParentSquare feeds and FRESH need no edits.

The invariant already has its guard. `stg_finalsite__contacts` carries a
`unique` test on `finalsite_enrollment_id` and
`stg_finalsite__contact_relationships` a
`dbt_utils.unique_combination_of_columns`. Today they pass trivially; under this
design they are what fails loudly if the dedupe regresses, before
`int_finalsite__student_address_of_record` or the `is_primary` picks in #4616 /
#4617 / #4680 see a duplicated row.

### 4. Scheduling

A library factory keeps all four districts on one implementation:

```python
@schedule(
    name=f"{code_location}__finalsite__contacts__daily_asset_job_schedule",
    cron_schedule=["15 0 * * *", "0 12 * * *"],
    execution_timezone=str(local_timezone),
    target=[contacts_asset],
)
def _schedule(context: ScheduleEvaluationContext):
    yield RunRequest(
        partition_key=context.scheduled_execution_time.date().isoformat(),
        tags={MAX_RUNTIME_SECONDS_TAG: str(900)},
    )
```

- `run_key` stays `None`. Both ticks target the same partition key; a `run_key`
  equal to the partition key would make Dagster's idempotency swallow the 12:00
  run.
- The schedule name is byte-identical to today's. Renaming mints a new Dagster+
  schedule object and abandons its status and tick history, which is why "daily"
  stays in a name that now means twice daily.
- `MAX_RUNTIME_SECONDS_TAG` drops 3600 to 900.
- The `finalsite_api` pool stays at limit 1. #4408 is untouched.
- 00:15 rather than 00:30 leaves ~30 minutes of margin before the 01:00 account
  sync, and both avoid top-of-hour, where GKE Autopilot fan-out adds 3-9 minutes
  of step-pod scheduling wait.

## Cutover

The external glob `contacts/*` matches recursively, so while both the legacy
root object and partition files exist the table unions them and every `id`
appears twice.

1. Pause the four contacts schedules in Dagster+ (manual, UI).
1. Merge the PR; let the deploy land.
1. Seed each district: one manual materialization with the full-pull flag,
   roughly 35 minutes serialized through the pool.
1. Delete the legacy `.../finalsite/contacts/data` object in each of the four
   buckets (manual, `gsutil`).
1. Run `stage_external_sources` plus a metadata cache refresh, then rebuild
   staging and downstream.
1. Verify row counts against the pre-cutover baseline: kippmiami 7,688,
   kippnewark 25,052.
1. Resume the schedules at 00:15 and 12:00.

Expect a transient test failure between steps 3 and 4: the seed bumps the
source's data version, the automation sensor rebuilds staging while duplicates
exist, and the `unique` test fails. That ordering is deliberate. Deleting the
root object first would leave the table empty, and staging would build 0 rows
and ship empty files to DeansList, ParentSquare and Focus. A loud failed test
beats a silent empty shipment.

## Known limitations

- **Hard deletes leak.** Latest-per-`id` dedupe never forgets a contact whose
  record vanishes from Finalsite: its last-seen partition stays newest for that
  `id`. Scope exits (withdrawn, graduated) are unaffected because they are
  status updates, not deletions. Observed rate: kippmiami `record_count` ran
  7,679 to 7,691 to 7,688 across consecutive pulls, so a few a day. Accepted
  deliberately; revisit only if it becomes a problem.
- **Schema heterogeneity is now a recurring chore.** When Avro files with
  different schemas coexist under one external table, a query scanning both
  resolves a single reader schema and drops the newer field for the whole scan;
  the column reads NULL everywhere and no cache refresh fixes it. Because
  staging scans full partition history, every future field added to
  `CONTACTS_SCHEMA` requires re-encoding the entire history with
  `scripts/reencode_avro_partitions.py`. Today, with one object replaced whole,
  a schema addition heals on the next pull.
- **The #4151 metadata-cache race is inherited, not introduced.**
  `refresh_external_metadata_cache` returning DONE does not mean queryable-fresh
  (lag seconds to hours, non-monotonic), so the 00:15 to 01:00 chain carries a
  tail risk that scheduling margin cannot fully close. The same race exists
  today against the overwritten single object.
- **Partition count grows without pruning.** One object per district per day. At
  BigQuery's scale this is years away from mattering, so no pruning is designed.
- **A day where BOTH ticks fail does not self-heal.** `since` is derived from
  the partition key, so partition `D+1` asks for `since = D` and never
  re-requests changes made on `D-1`. One failed tick is harmless — the other
  tick that day covers the same window — but a fully-missed day leaves that
  window unasked, and the affected contacts hold stale values until the vendor
  happens to touch them again. Recovery is to backfill the missing partition,
  which requests its own `D-1` window. **Nothing currently alerts on a missing
  partition**, so this depends on someone noticing the gap in the Dagster UI.
  The old full-snapshot design was completely self-healing here; this is a new
  operational trap accepted in exchange for the incremental cost saving.

## Acceptance criteria

| Criterion (#4715)                                                                | How this design meets it                                                                                                                                                                               |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A normal tick requests only changed contacts and issues far fewer requests       | 81 pages vs ~1,002 for kippnewark; 40 vs ~308 for kippmiami                                                                                                                                            |
| A relationship-only change is picked up                                          | Confirmed by the probe: 44 relationship-signature diffs on kippnewark, 2 on kippmiami, all present without `since_includes_expanded`                                                                   |
| A changed or new contact lands with the same column values                       | Same Avro schema, same projection; verified by the pre/post row-count and value comparison in cutover step 6                                                                                           |
| A deleted contact stops appearing within one full-refresh cycle                  | **Not met, deliberately.** No full refresh; see Known limitations                                                                                                                                      |
| A failed run does not advance the watermark; a failed TICK recovers              | The watermark is the partition key, so a failed run writes no partition. One failed tick is covered by the other tick that day. A day where BOTH ticks fail does NOT self-heal — see Known limitations |
| Asset keys and dbt source names unchanged; downstream builds with no model edits | Asset key and source name unchanged; edits confined to the two staging models                                                                                                                          |
| kippnewark's `MAX_RUNTIME_SECONDS_TAG` can be dropped or reduced                 | 3600 to 900                                                                                                                                                                                            |

## Out of scope

- `status_report`. It arrives by SFTP and is already school-year partitioned.
- The `finalsite_api` pool limit and the shared-IP 403 (#4408).
- Bounded retry in `_request` (#4494).
- Un-pausing kippnewark's ParentSquare extract schedule, which ships STOPPED for
  reasons unrelated to contacts freshness.
