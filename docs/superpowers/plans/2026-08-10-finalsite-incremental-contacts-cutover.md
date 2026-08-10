# Finalsite incremental contacts: cutover runbook

Refs #4715. Run these in order. Steps marked **manual** need a human — they
touch production GCS or the Dagster+ UI.

The external glob `contacts/*` matches recursively, so while both the legacy
root object and partition files exist the table unions them and every `id`
appears twice at the storage layer. That window is steps 3 to 5.

## Before you merge

dbt Cloud CI will be **red** on this PR, by design:

- CI runs `dbt build` only — it never runs `stage_external_sources` — so it
  reads the pre-cutover production `finalsite.contacts` external table, which
  has no `_dagster_partition_*` columns. `stg_finalsite__contacts` therefore
  fails in CI and cannot pass until the cutover in step 6 runs.
- Merging requires overriding that required check.
- Every prod dbt model downstream of contacts is broken from merge until step 6
  completes. Schedule the merge and the cutover together — do not merge and walk
  away.

## 1. Record the pre-cutover baseline (manual)

```sql
select count(*) as contacts, count(distinct id) as ids
from `teamster-332318.kippnewark_finalsite.contacts`
```

Repeat for `kippcamden`, `kippmiami`, `kipppaterson`. Expected around 25,052
(kippnewark) and 7,688 (kippmiami). Keep these numbers for step 6.

## 2. Pause the schedules (manual, Dagster+ UI)

Stop all four `<location>__finalsite__contacts__daily_asset_job_schedule`
schedules. Do not rename them.

## 3. Merge the PR and let the deploy land

Confirm every `dagster-cloud-deploy / deploy` check-run reaches a terminal
conclusion — a shared-library change redeploys every consuming location, so
expect one same-named check per location.

## 4. Seed one full partition per district (manual, Dagster+ UI)

For each location, materialize `<location>/finalsite/contacts` for partition
`2026-08-11` with run config:

```yaml
ops:
  <location>__finalsite__contacts:
    config:
      full_pull: true
```

Override the run's `dagster/max_runtime` tag to `3600` for these four runs only
— a full pull is ~20 minutes for kippnewark, well past the new 900s default.
They serialize through the `finalsite_api` pool, so budget ~35 minutes total.

Verify each run's `record_count` metadata matches step 1's baseline, and that
its `since` metadata reads `FULL PULL`.

The partition key `2026-08-11` must equal the asset's configured
`DailyPartitionsDefinition(start_date=...)` in all four code locations'
`finalsite/assets.py` — seeding the wrong partition key puts the base data on a
partition the schedule will never revisit. If the cutover happens later than
`2026-08-11`, bump `start_date` in all four `finalsite/assets.py` files and this
runbook's partition key together, in the same change.

## 5. Delete the legacy root object (manual, destructive)

Do not run this step until step 4's seed runs are verified to have landed
(`record_count` matched step 1's baseline for all four locations). Deleting the
root object before the seed is confirmed would leave the external table empty,
and `stg_finalsite__contacts` would build to zero rows — the downstream feeds
would then ship empty files to DeansList, ParentSquare and Focus instead of
failing loudly. That is the reason for the step 4 → step 5 order; do not reorder
these under time pressure.

One per bucket. Check before deleting:

```bash
gsutil ls -l gs://teamster-kippnewark/dagster/kippnewark/finalsite/contacts/data
gsutil rm gs://teamster-kippnewark/dagster/kippnewark/finalsite/contacts/data
```

Repeat for `teamster-kippcamden`, `teamster-kippmiami`, `teamster-kipppaterson`.

Confirm only partition directories remain:

```bash
gsutil ls gs://teamster-kippnewark/dagster/kippnewark/finalsite/contacts/
```

Expected: only `_dagster_partition_fiscal_year=.../` entries, no bare `data`.

## 6. Re-stage the external source and rebuild staging

```bash
uv run dbt run-operation stage_external_sources \
  --project-dir src/dbt/kippnewark --args "select: finalsite.contacts"
uv run dbt build --project-dir src/dbt/kippnewark --select stg_finalsite__contacts
```

Repeat the `stage_external_sources` call for `kippcamden`, `kippmiami`, and
`kipppaterson` before their `dbt build`.

From the moment this PR merges (step 3) until this step finishes, expect
`stg_finalsite__contacts` to fail to **build**, not to fail a test. The
production `finalsite.contacts` external table currently has zero
`_dagster_partition_*` columns (confirmed via `INFORMATION_SCHEMA`:
`status_report` has one, `contacts` has none), and `stg_finalsite__contacts` now
orders by `_dagster_partition_date`. Until `stage_external_sources` recreates
the table over the Hive-partitioned files, any query against
`stg_finalsite__contacts` — and everything downstream of it — errors with
`Unrecognized name: _dagster_partition_date`. The window to minimize is merge →
re-stage, not seed → delete; that's why "Before you merge" above says to
schedule the merge and this step together.

Then confirm the grain and the count, with `--nouse_cache` so the results cache
cannot mask a stale read:

```sql
select count(*) as rows, count(distinct finalsite_enrollment_id) as ids
from `teamster-332318.kippnewark_finalsite.stg_finalsite__contacts`
```

`rows` must equal `ids`, and both must match step 1's baseline within a day of
churn. The `unique` test on `finalsite_enrollment_id` is the automated form of
this check.

## 7. Verify downstream consumers

`stg_finalsite__contacts` dedupes to one row per contact, but nothing that
assumes that grain could be build-verified before now — the partition column
didn't exist until step 6. Build and test the real consumers:

```bash
uv run dbt build --project-dir src/dbt/kippnewark --select stg_finalsite__contacts+
```

Repeat with `--project-dir src/dbt/<location>` for `kippcamden`, `kippmiami`,
and `kipppaterson`. A pass proves the deduped one-row-per-contact grain holds
through every model built on it, specifically:

- `int_finalsite__student_contacts`
- `int_finalsite__student_address_of_record`
- the singular tests `stg_finalsite__contact_relationships__caregiver_is_adult`
  and `stg_finalsite__contact_relationships__single_primary`

If any of these fail, the cutover has not actually restored one row per contact
— do not resume schedules until they pass.

## 8. Resume the schedules (manual, Dagster+ UI)

Start all four schedules. The next tick is 00:15 or 12:00 ET.

## 9. Confirm the first incremental tick

After the first 00:15 run, check its metadata: `since` should read the previous
day's date, and `record_count` should be in the low thousands, not the tens of
thousands. Then confirm the 01:00 Google Directory sync and 01:25 DeansList ship
read same-day contacts.
