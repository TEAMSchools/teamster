# Focus empty-table materialization — design

Issue: [#4740](https://github.com/TEAMSchools/teamster/issues/4740). Builds on
[#4733](https://github.com/TEAMSchools/teamster/issues/4733).

## Problem

11 of the 77 configured Focus tables are absent from
`dagster_kippmiami_dlt_focus` because they hold no rows in Focus yet:

`attendance_day`, `attendance_notes`, `attendance_period`,
`discipline_incidents`, `discipline_incidents_join_referrals`,
`gradebook_grades`, `referral_code_offenses`, `student_groups`,
`student_standard_grades`, `students_join_groups`, `students_join_students`.

All 11 are already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`, but none has a staging
model — a contract-enforced staging model cannot be built against a table that
does not exist. Only 64 of 77 configured tables are staged, and every
newly-populated Focus table needs a dbt change before its data is usable.

### Cause

`dlt/extract/extract.py::_handle_empty_tables` writes an empty file only for a
`replace` table that has previously **seen data**
(`schema.data_tables(seen_data_only=True)`). A never-loaded table produces no
file at all, normalize drops the package, and nothing reaches BigQuery. The
asset succeeds with `jobs: []` — an absence, not a failure.

## Goal

A configured Focus table with zero source rows exists in BigQuery as an empty,
correctly typed table, so its staging model can be written before its data
arrives.

Non-goals: changing how populated tables load, and any Illuminate or PowerSchool
behavior (see _Out of scope_).

## Approach

Three coupled changes, all in `src/teamster/libraries/dlt/focus/assets.py`
except the migration.

### 1. Materialize the schema for a never-loaded table

`sql_database` opens every table by yielding
`dlt.mark.with_hints([], dlt.mark.make_hints(**hints))` — a plain empty list
that registers the reflected schema and is then discarded. Yielding
`dlt.mark.materialize_table_schema()` instead makes dlt create the table from
those same hints.

Reaching that yield means driving the exported `table_rows` generator inside our
own resource rather than calling `sql_database`, which is the pattern
`libraries/dlt/powerschool/` already uses and `libraries/dlt/CLAUDE.md`
documents. The wrapper must keep `reflection_level="full_with_precision"`,
`table_adapter_callback=remove_nullability_adapter`, and
`type_adapter_callback=interval_to_microseconds_adapter`, or reflected types and
nullability regress.

### 2. Enable dlt's row-id columns

```python
dlt.config["normalize.parquet_normalizer.add_dlt_id"] = True
dlt.config["normalize.parquet_normalizer.add_dlt_load_id"] = True
```

Set in the op body, not at module import: each step runs in its own pod, so this
cannot leak into another pipeline. `libraries/dlt/powerschool/` sets
`dlt.config["extract.workers"]` the same way.

This is load-bearing, not tidying. `materialize_table_schema()` runs through
dlt's **object** path, which always injects `_dlt_id` and `_dlt_load_id` as
REQUIRED. With the knobs at their defaults the arrow data path omits both, so
the first real load into an empty-created table fails terminally with
`Field _dlt_load_id is missing in new schema`.

### 3. One-time migration of the 66 populated tables

BigQuery rejects adding a REQUIRED column to an existing table
(`Cannot add required fields to an existing schema`), so the populated tables
must be recreated rather than altered. Passing `refresh="drop_resources"` to
`dlt.run()` makes dlt drop and recreate the tables of the resources in that run
— no hand-written DDL, and no warehouse access needed by a person.
`drop_resources` rather than `drop_sources` because each Focus asset runs one
resource against a shared `focus` pipeline; `drop_sources` would also discard
the pipeline's stored schema and state for tables the run does not select.

Cost is one full reload from Focus, which `replace` already performs daily.

**Mechanism**: the op takes a Dagster `Config` with a `refresh` field defaulting
to `None`, and forwards it to `dlt.run()` only when set. The migration is then a
one-off launch with run config, not a code change that must be deployed and
reverted. `libraries/dlt/powerschool/` already uses op run-config this way
(`PowerSchoolDltConfig`).

```python
class FocusDltConfig(Config):
    refresh: str | None = None
```

Every scheduled run keeps the default and behaves exactly as today.

## Consequences

- Every Focus table permanently gains `_dlt_id` (a per-row hash) and
  `_dlt_load_id`. No contract breaks: 61 of 64 staging models enumerate columns
  explicitly, and the 3 that use `select *` read through a source CTE and then
  project explicitly (`stg_focus__address`, `stg_focus__students_join_people`,
  `stg_focus__students_join_address`).
- Column **order** differs between a table created empty (`_dlt_*` first) and
  one created by a data load (`_dlt_*` last). BigQuery matches load files by
  name, and every staging model projects explicitly, so this is cosmetic.
- During the migration a table is dropped before it reloads. Focus dbt staging
  models fail if they build in that window, so the run wants a quiet hour, and
  drop plus load must be the same run.

## Verification already performed

Probes against BigQuery in a scratch dataset, dlt 1.29.1. Scripts are in
`.claude/scratch/` (`probe_a2_bigquery.py`, `probe_migration_lifecycle.py`).

| Sequence                                | Knobs off                             | Knobs on |
| --------------------------------------- | ------------------------------------- | -------- |
| Add row-id columns to an existing table | rejected — cannot add required fields | n/a      |
| Create empty, then load first real data | rejected — `_dlt_load_id` is missing  | passes   |
| Recreated table: load, reload, go empty | passes                                | passes   |
| Created empty: data, empty, data again  | fails at first data                   | passes   |

Local extract-plus-normalize probes (no credentials) additionally showed the
materialize path and the arrow path emit **identical types and modes for every
shared column**, so an empty-created table accepts the later load on type
grounds as well as column-set grounds.

One gap, to close during implementation: the lifecycle probe's resource carried
no column hints, so its empty table started with only the `_dlt_*` columns and
the first data load _added_ the data columns. Production reflects real hints, so
the empty table is typed from the start. Re-run the lifecycle probe with column
hints before relying on it.

## Testing

- Extend `tests/libraries/` with offline factory-wiring tests, in the style of
  `test_dlt_replace_loader_file_format.py`: assert the wrapper resource yields
  `materialize_table_schema()` when `table_rows` produces nothing, and that both
  `dlt.config` knobs are set when the asset body runs.
- Extend the local extract-plus-normalize probe with the typed-empty-table case
  named above.
- Post-migration warehouse checks: all 77 configured tables present; the 66
  previously-populated tables retain row counts within normal daily drift; the
  11 new tables exist with 0 rows and their reflected column sets.
- `dbt build` the Focus staging models against the migrated dataset before the
  new staging models are written.

## Sequencing hazard for the same-PR staging models

The 11 staging models are contract-enforced, so their `properties.yml` needs
exact column names and BigQuery types — which normally come from the
materialized table. That creates an ordering problem:

- The tables do not exist until the new code runs.
- Creating them early from a branch deployment writes to the **prod** dataset
  (dlt has no branch-deployment redirect, per `focus/CLAUDE.md`), and once
  created they carry REQUIRED `_dlt_*` columns. Prod is still running the old
  code, whose loads omit those columns, so the next scheduled Focus run would
  fail on those tables until this PR merges.

Three ways to resolve, to be decided before implementation:

1. Split the work: pipeline change plus migration in this PR, staging models in
   a follow-up written against real materialized tables. Removes the hazard
   entirely.
1. Keep one PR and derive the contract types from the reflected Postgres schema
   (dlt's type mapping is deterministic, and `remove_nullability_adapter` plus
   `interval_to_microseconds_adapter` fix the two non-obvious cases). Verify by
   building the staging models immediately after the post-merge migration; a
   mistyped column fails the build, not the load.
1. Keep one PR and capture the reflected schema first via a throwaway
   branch-deployment run that logs column names and types without creating
   tables, then write contracts from that log.

Option 1 is recommended. Option 2 is viable but front-loads type risk into
review; option 3 costs throwaway code.

## Out of scope

- **Illuminate** — exactly one configured table is absent
  (`dna_repositories.repository_463`), and `illuminate_repository_unpivot`
  already emits a typed empty `SELECT` when the source is missing, so its asset
  is healthy. Applying this design there would let that `{% if cols %}` fallback
  be deleted; that is a follow-up, not part of this work.
- **PowerSchool** — omits `autodetect_schema=True`, so its loads carry a
  dlt-managed schema and an empty file loads without BigQuery inference. It
  never had this failure mode and needs no change.

## Rollout

Current decision is one PR containing both the pipeline change and the 11
staging models, so their contract types come from the reflected Postgres schema
(_Sequencing hazard_, option 2) and are proven by the post-merge build.

1. Merge the PR.
1. Confirm the `kippmiami` code location loads the new commit.
1. Launch the Focus asset job once with run config `refresh: drop_resources`, at
   a quiet hour. All 66 populated tables are recreated with the row-id columns
   and the 11 empty ones are created in the same run.
1. Confirm all 77 tables exist, the 66 retain their row counts, and the 11 are
   empty with the expected column sets.
1. Build the Focus staging models, including the 11 new ones. A mistyped
   contract column fails here, which is the intended catch point for option 2.

If the hazard decision moves to option 1 instead, steps 1 through 4 carry the
pipeline change alone and the staging models follow in a second PR written
against the now-materialized tables.
