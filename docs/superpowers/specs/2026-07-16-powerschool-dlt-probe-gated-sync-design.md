# PowerSchool dlt probe-gated sync (kipppaterson)

Tracked in [#3807](https://github.com/TEAMSchools/teamster/issues/3807).
Redesigns the kipppaterson dlt PowerSchool ingestion before PR #4415 merges.

## Problem

The current design blindly full-replaces all 37 "intraday" tables every 15
minutes plus 11 gradebook tables nightly:

- One `@dlt_assets` **per table**, each with its own `dlt.pipeline` and its own
  paramiko SSH tunnel, `write_disposition="replace"`
  (`src/teamster/libraries/dlt/powerschool/assets.py`).
- ~3,500 step pods/day re-pulling mostly unchanged data.
- 14 tables with no change-cursor column run intraday for no reason.
- A concurrency-pool throttle exists only to protect the shared dlt state table
  from per-table pipeline fan-out (429s).

A branch-deployment test (run `6d162356`, deployment
`b5544f366f506d8859ba091e2d7476398807472d`) showed the current design is fast
enough (37/37 tables in ~202s wall-clock, unthrottled) — the redesign case is
**waste and correctness**, not wall-clock.

## Design

### One multi-asset, gate in the op via `with_resources`

One factory builds **one `@dlt_assets`** over one `@dlt.source` containing all
48 table resources, one `dlt.pipeline`, one dlt state, landing in the existing
`dagster_kipppaterson_dlt_powerschool` dataset. Asset keys gain a `sis` segment
(`kipppaterson/powerschool/sis/{table}`, parallel to the
`powerschool/enrollment/*` namespace); BigQuery table names and the dbt
`staging/dlt` variant are unchanged. `PowerSchoolODBCResource` is eliminated for
Paterson.

The change gate lives in the **op body**, not inside each resource. A spike
(2026-07-16, see Spike section) established that a `write_disposition="replace"`
resource which yields zero rows still **truncates** its destination table — so
an "unchanged" table cannot be skipped by returning early from inside the run.
Instead the op probes, computes the changed set, and passes only the changed
resources to `pipeline.run(...)` via `source.with_resources(*changed)`;
unselected resources are never in the run, so their tables are left untouched
(spike-verified). This is one Dagster run, one pod, one tunnel per tick — no
sensor, no second run:

```python
def _assets(context, dlt, ssh_powerschool):
    with ssh_powerschool.open_ssh_tunnel_paramiko():
        dlt_pipeline.sync_destination()                  # restore stored sigs (metadata read, not a load)
        stored = _stored_signatures(dlt_pipeline)        # per-resource resource_state from last run
        engine = sa.create_engine(_oracle_connection_url())
        current = {t: probe_signature(conn, t.name, t.cursor_column) for t in selected if t.cursor_column}
        changed = [t for t in selected
                   if t.cursor_column is None             # no cursor -> always load when selected
                   or current[t.name] != stored.get(t.name)]  # drift or first run
        if not changed:
            return                                        # op yields nothing; no load this tick
        yield from dlt.run(
            context=context,
            dlt_source=source_for(changed, current),      # each resource writes its sig to resource_state
            write_disposition="replace",
        )
```

- **Probe**: `SELECT COUNT(*), MAX({cursor_column}) FROM {table}` — one shared
  SQLAlchemy engine over the single paramiko tunnel; sub-second per table.
- **Compare**: equality against the stored signature read from dlt
  `resource_state` (persisted in BigQuery `_dlt_pipeline_state`; restored by
  `sync_destination()`, spike-verified round-trip). Equality (not `>`) also
  catches cursor regressions (newest row deleted).
- **Signature store (`resource_state`)**: each selected resource writes its
  just-probed signature into `dlt.current.resource_state()["signature"]` (the op
  passes the probed value in) and then `yield from sql_table(...)` (pyarrow,
  `full_with_precision`, existing `oracle_number_adapter` +
  `remove_nullability_adapter`), `replace` truncate+load (free in BigQuery). The
  state write rides with the load package, so signature and data commit
  atomically — a run that fails before load re-detects the change next tick.
- **`cursor_column: null`** (14 tables) → probe skipped, table is always in the
  changed set when selected. These are only ever scheduled nightly.

Why the two comparisons: `MAX(cursor)` catches inserts/updates (PowerSchool
stamps `transaction_date`/`whenmodified` on modify); `COUNT(*)` catches deletes.
This mirrors Newark's proven `evaluate_asset_staleness` semantics
(`src/teamster/libraries/powerschool/sis/odbc/utils.py`) with a strictly safer
compare.

### Not using `dlt.sources.incremental`

`dlt.sources.incremental` is a row filter (only-new rows, feeding append/merge).
We want full-replace payloads gated on a change signal, so the dlt-native
mechanism is `resource_state` — the same store `incremental` uses under the
hood. BigQuery `MERGE` is explicitly rejected: real scan cost, whereas `replace`
is a free truncate+load.

### Dagster surface

- The op probes and loads in one pod (see op body above). Because only the
  changed resources are in the `pipeline.run`, dagster-dlt emits a
  `MaterializeResult` only for the changed set — unchanged tables produce no
  materialization, so no spurious downstream dbt automation triggering, with no
  event-filtering needed. `@dlt_assets` is `multi_asset(can_subset=True)`
  (dagster-dlt 0.29.13), so the runtime-narrowed run is legal.
- Per-table probe outcomes are logged (`context.log.info`) so each tick's
  changed-set is auditable.
- **Schedules subset the multi-asset by tier** (cadence is pure schedule
  config). The schedule fires the op with `selected_asset_keys` = its tier; the
  op probes those and narrows further at runtime to the changed subset via
  `source.with_resources(*changed)`. dagster-dlt's own `is_subset` filter
  intersects the explicit source with `selected_asset_keys` — changed ⊆
  selected, so it passes through unchanged:
  - intraday `*/15 * * * *` → the 23 cursor tables listed below
  - nightly `0 2 * * *` → 11 gradebook tables + 14 no-cursor tables
- Retiering a table = editing the `schedule_tier` value read by `schedules.py`;
  the asset definition doesn't change.
- The `dlt_powerschool_kipppaterson` pool is kept at **limit 1** as insurance
  against a wedged run piling up duplicates; `dagster/max_runtime` sized
  generously above the worst case (see Baseline).
- No partitioning. The fiscal-year-partition capability was considered and
  **discarded** — reintroduce only if a table's full replace becomes an actual
  problem (Paterson's `attendance` is ~1/10th Newark's).

### Config

`config/assets.yaml` stays the single source of truth, one entry per table:

```yaml
assets:
  - table_name: students
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: attendance_code
    cursor_column: null
    schedule_tier: nightly
```

`load_strategy` is dropped (everything is `replace`). The factory builds the one
assets def from the full list; `schedules.py` builds tier target lists from
`schedule_tier`.

### Cursor map

Source of truth: kippnewark's per-table config
(`code_locations/kippnewark/powerschool/config/*.yaml` + `assets.py`), verified
2026-07-16. Note the Newark filenames are swapped relative to their content:
`assets-transactiondate.yaml` holds the FY-partitioned trio; `assets-full.yaml`
holds the full-pull tables with gating cursors.

| Tier (schedule)        | Cursor             | Tables                                                                                                                                                                                                                                                       |
| ---------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| intraday, gated        | `transaction_date` | `attendance`, `storedgrades`, `pgfinalgrades`, `cc`, `students`, `courses`, `schools`, `sections`, `termbins`, `terms`                                                                                                                                       |
| intraday, gated        | `whenmodified`     | `gradescaleitem`, `roledef`, `s_nj_crs_x`, `s_nj_ren_x`, `s_nj_stu_x`, `s_stu_x`, `schoolstaff`, `sectionteacher`, `studentcorefields`, `studentrace`, `u_studentsuserfields`, `users`, `userscorefields`                                                    |
| nightly, gated         | `whenmodified`     | `assignmentcategoryassoc`, `assignmentscore`, `assignmentsection`, `districtteachercategory`, `gradecalcformulaweight`, `gradecalcschoolassoc`, `gradecalculationtype`, `gradeformulaset`, `gradeschoolconfig`, `gradeschoolformulaassoc`, `teachercategory` |
| nightly, unconditional | none               | `attendance_code`, `attendance_conversion_items`, `bell_schedule`, `calendar_day`, `cycle_day`, `fte`, `gen`, `log`, `reenrollments`, `spenrollments`, `studenttest`, `studenttestscore`, `test`, `testscore`                                                |

(`attendance`, `storedgrades`, `pgfinalgrades` are FY-partitioned in Newark; for
Paterson they are plain full-pull gated tables.)

Out of scope, noted as follow-up: Newark trims columns on `cc`,
`u_studentsuserfields`, and `log` via `select_columns`; Paterson pulls full
tables.

## Edge cases

- **Table emptied at source** (count → 0): `COUNT(*)` drift puts the table in
  the changed set; it runs, yields zero rows, and `replace` truncates it to
  empty — the correct result, automatically. No special handling. (This is the
  same truncate-on-zero-yield behavior that ruled out the in-resource gate;
  under op-gate it is exactly what we want.)
- **Probe blind spot**: a modification that changes neither `COUNT(*)` nor the
  cursor column (e.g. direct DBA edits suppressing `whenmodified`) is missed.
  Accepted — Newark's prod probe has had the same blind spot for years.
- **Migration**: the new single pipeline name starts with empty state, so the
  first run full-loads all 48 tables and seeds signatures. Old per-table
  pipeline state rows in `_dlt_pipeline_state`/`_dlt_loads` are inert; cleanup
  optional.

## Baseline (measured 2026-07-16)

From branch-deployment run `6d162356` (37 intraday tables, separate pods, 37/37
success, ~202s wall-clock):

- Sum of all 37 step durations: ~657s; the 23 redesign-intraday tables: ~429s.
- Per-step floor ~10.5s is fixed overhead (pipeline init, BQ schema sync,
  load-job latency) paid per pod today but once per run after the collapse; dlt
  parallelizes normalize and load (up to 20 concurrent BQ load jobs) within one
  `pipeline.run`.
- Estimated worst case (all 23 intraday tables changed, one pod): ~3-5 min, ~7
  min ceiling. All-48 catch-up: under ~10 min serialized. Typical tick (probes +
  a few loads): ~1-2 min including pod startup.

These estimates are derived, not measured — the spike times the real thing.

## Spike (executed 2026-07-16, local duckdb)

1. A `replace` resource yielding zero rows **truncates** its destination table
   (3 rows → 0). This **REJECTED the in-resource gate** and drove the pivot to
   the op-gate design above.
1. `source.with_resources(<subset>)` leaves unselected tables untouched (an
   unselected table's 3 rows were preserved while another resource loaded) —
   confirms the op-gate mechanism.
1. `resource_state` round-trips through a fresh pipeline instance via
   `sync_destination()` (the stored signature was restored) — confirms the
   signature store survives a new pod.
1. Timing of the collapsed all-tables run: deferred to the branch-deployment E2E
   (Task 6); local duckdb timing is not representative of Oracle + BigQuery.

## Testing

- pytest: gating logic (signature compare, changed-set selection, no-cursor
  always-selected, first-run all-changed) against a mocked engine/state.
- `uv run dagster definitions validate` for
  `teamster.code_locations.kipppaterson.definitions`.
- Branch-deployment end-to-end: (a) only changed tables materialize, (b) BQ row
  counts match Oracle, (c) an idle second run materializes nothing.
