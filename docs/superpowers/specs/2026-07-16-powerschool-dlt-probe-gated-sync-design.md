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

### One multi-asset, gate inside each dlt resource

One factory builds **one `@dlt_assets`** over one `@dlt.source` containing all
48 table resources, one `dlt.pipeline`, one dlt state, landing in the existing
`dagster_kipppaterson_dlt_powerschool` dataset. Asset keys
(`kipppaterson/powerschool/{table}`), BigQuery table names, and the dbt
`staging/dlt` variant are unchanged. `PowerSchoolODBCResource` is eliminated for
Paterson.

Each table is a custom `@dlt.resource` we author (replacing bare `sql_table()`
wrapping), so `dlt.current.resource_state()` is writable:

```python
def table_resource(t):
    @dlt.resource(name=t.name, write_disposition="replace")
    def _resource():
        if t.cursor_column is not None:                  # gated path
            state = dlt.current.resource_state()
            sig = probe(t)                               # COUNT(*) + MAX(cursor)
            if sig == state.get("signature"):
                return                                   # unchanged: no rows, no load job
            state["signature"] = sig
        yield from sql_table(...)                        # full pull, replace
    return _resource
```

- **Probe**: `SELECT COUNT(*), MAX({cursor_column}) FROM {table}` — one shared
  SQLAlchemy engine over the single paramiko tunnel; sub-second per table.
- **Compare**: equality against the stored signature in dlt resource state
  (restored from BigQuery `_dlt_pipeline_state` automatically;
  `restore_from_destination` is the default, and dagster-dlt's
  `drop()`-then-sync handles fresh pods). Equality (not `>`) also catches cursor
  regressions (newest row deleted).
- **Drift or no stored signature** → write new signature to state, full
  `SELECT *` pull via dlt's built-in `sql_table()` (pyarrow backend,
  `full_with_precision`, existing `oracle_number_adapter` +
  `remove_nullability_adapter`), `replace` truncate+load (free in BigQuery).
- **No drift** → yield nothing: no extraction, no load job, table untouched.
  State needs no write (already equal).
- **`cursor_column: null`** (14 tables) → probe skipped, always full replace.
  These are only ever scheduled nightly.

Why the two comparisons: `MAX(cursor)` catches inserts/updates (PowerSchool
stamps `transaction_date`/`whenmodified` on modify); `COUNT(*)` catches deletes.
This mirrors Newark's proven `evaluate_asset_staleness` semantics
(`src/teamster/libraries/powerschool/sis/odbc/utils.py`) with a strictly safer
compare.

State atomicity falls out of dlt semantics: resource state commits with the load
package, so a run that fails before load re-detects the change next tick.

### Not using `dlt.sources.incremental`

`dlt.sources.incremental` is a row filter (only-new rows, feeding append/merge).
We want full-replace payloads gated on a change signal, so the dlt-native
mechanism is `resource_state` — the same store `incremental` uses under the
hood. BigQuery `MERGE` is explicitly rejected: real scan cost, whereas `replace`
is a free truncate+load.

### Dagster surface

- The op body opens the tunnel once and iterates
  `dlt.run(context=context, write_disposition="replace")`, **yielding only
  events for tables that actually loaded** (presence in
  `load_info`/`rows_loaded`). Unchanged tables produce no materialization — no
  spurious downstream dbt automation triggering. `@dlt_assets` is
  `multi_asset(can_subset=True)` (dagster-dlt 0.29.13), so partial yield is
  legal.
- Per-table probe outcomes are logged (`context.log.info`) so each tick's
  changed-set is auditable.
- **Schedules subset the multi-asset** (cadence is pure schedule config;
  `dagster-dlt` maps `context.selected_asset_keys` →
  `source.with_resources(...)`):
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

- **Table emptied at source** (count → 0): drift is detected but zero rows yield
  — `replace` won't truncate. Handle explicitly: truncate the BigQuery table via
  the pipeline's `sql_client` (BigQuery `TRUNCATE TABLE` is free) and persist
  the new signature.
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

## Spike (before implementation, on the branch deployment)

1. Confirm a `replace` resource yielding zero rows produces no load job and does
   not truncate the destination table.
1. Confirm a state-only change (empty-table edge) still commits a state update
   to `_dlt_pipeline_state`.
1. Time the collapsed all-tables single-pipeline run.

## Testing

- pytest: gating logic (signature compare, no-cursor bypass, empty-table
  truncate path, first-run seeding) against a mocked engine/state.
- `uv run dagster definitions validate` for
  `teamster.code_locations.kipppaterson.definitions`.
- Branch-deployment end-to-end: (a) only changed tables materialize, (b) BQ row
  counts match Oracle, (c) an idle second run materializes nothing.
