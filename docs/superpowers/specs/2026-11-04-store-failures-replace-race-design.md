# Stored test failures: replace without dropping

Refs [#6254](https://github.com/TEAMSchools/teamster/issues/6254).

## Why

Two Dagster dbt runs sometimes run the same test at the same moment. dbt's
built-in `test` materialization deletes the stored-failure relation and then
creates it again. A run that reads the relation in the gap fails with
`Not found: Table`. Two runs that both find it missing and both create it fail
with `409 Already Exists`. Kipptaf saw 4 such failures in 60 days. The automatic
run retry recovered each one, but each one adds noise to the day-2 report and
delays downstream assets.

The stored failures must stay. Point-of-entry tests depend on them: staff
retrieve the violating records from `*_dbt_test__audit` and fix them in the
source system.

## Goals

- No race failures on stored-failure relations in any of the 5 `kipp*` projects.
- Done means this query returns 0 rows for 30 days after deploy:
  `REGEXP_CONTAINS(error_result.message, r'^(Not found|Already Exists): Table teamster-332318:[a-z_]*dbt_test__audit\.')`
  on `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`.

## Non-goals

- Changing which tests run in which Dagster run (indirect selection).
- Keeping a history of past failures.
- Adding `meta.dagster.ref` to the 3 multi-parent singular tests that raced.
  That is a separate change and does not prevent the race.

## Anti-goals

- Any change to what the audit relations contain, or where they live.
- A silent divergence from dbt's materialization after a dbt upgrade.

## Evidence

- A race test against BigQuery used 2 writers and 4 readers on one view for 60
  seconds per arm. `create or replace view` alone had 0 failed reads out of 634
  and 0 write errors. Delete-then-create had 208 "Not found" reads out of 696
  and 2 `409 Already Exists` writes. Details are on #6254.
- Upstream, dbt v1 and the v2 engine both delete first. The behavior dates from
  [dbt-labs/dbt#3316](https://github.com/dbt-labs/dbt/pull/3316) ("It's not an
  atomic operation, since that's not the point"). In that change it was needed
  because `create_table_as` on the default adapter cannot replace an existing
  table. [dbt-labs/dbt#16343](https://github.com/dbt-labs/dbt/issues/16343) asks
  for replace-without-drop and is open with no fix.

## Approaches

1. **One copy in a shared local package, with a root stub in each project
   (chosen).** dbt 1.12 ignores a package's override of a built-in
   materialization unless the root project defines one
   (`require_explicit_package_overrides_for_builtin_materializations`, in
   `find_materialization_macro_by_name`). So each project gets a 3-line stub
   that returns the package's macro. One copy to compare on each dbt upgrade.
2. **The full copy in each project's `macros/`.** No new package, but 5
   identical copies of about 70 lines that can drift apart.
3. Rejected:
   - Store failures as tables: they take the same delete-then-create path.
   - Store failures only for opted-in tests: the point-of-entry tests that must
     keep storing failures would still race.
   - `DBT_INDIRECT_SELECTION=cautious`: multi-parent tests would almost never
     run.
   - A Dagster-side retry: fragile, because a real asset check would be reported
     twice.
   - Accepting the race: it leaves the noise and the delay.

## Design

- **Package.** A new macro-only local package, `src/dbt/dbt_overrides/` (my call
  on the name). It holds `macros/materializations/test.sql`: the installed
  dbt-adapters `test` materialization copied verbatim, declared
  `adapter='bigquery'`, with one change. It drops the old relation only when its
  type differs from the target type:
  `{% if old_relation and old_relation.type != target_relation.type %}`. A view
  replacing a view, or a table replacing a table, goes straight to
  `create or replace`.
- **Root stubs.** Each of the 5 projects (`kipptaf`, `kippnewark`, `kippcamden`,
  `kippmiami`, `kipppaterson`) adds `- local: ../dbt_overrides` to
  `packages.yml`. Each also adds `macros/materializations/test.sql`:
  `{% materialization test, adapter='bigquery' %}{{ return(dbt_overrides.materialization_test_bigquery()) }}{% endmaterialization %}`.
  This is kipptaf's first local package.
- **Drift guard (my call).** A pytest test that reads the installed dbt-adapters
  `test.sql`, applies the same one-line change, and asserts the result matches
  our copy. A dbt upgrade that changes the built-in then fails CI, and someone
  re-syncs the copy. Run it from `.github/workflows/pytest.yaml`, which already
  triggers on `uv.lock`, the file every dbt bump touches.
- **Upstream.** Comment on dbt-labs/dbt#16343 with this race as a correctness
  case, after the user approves the wording. Delete the package and stubs if dbt
  ships the change.
- **Docs.** One line in `src/dbt/CLAUDE.md` naming the package, and why a root
  stub is required.

## Left to the builder

- Confirm with `dbt compile` or a dev build that the root stub resolves the
  package macro, and that tests from source packages (for example powerschool
  tests in kippnewark) also use the override.
- Confirm that dbt Cloud CI, which builds kipptaf only, resolves
  `local: ../dbt_overrides`. Districts already use `../` local packages, but
  kipptaf has none yet.
- Prove the fix in dev: run the same stored-failure test from 2 concurrent
  `dbt test` invocations in a loop. Confirm 0 race errors, and confirm the same
  loop fails on the unpatched materialization.
- Whether `dagster-dbt project prepare-and-package` needs anything for the new
  package. The Docker image already copies all of `src/dbt/`.
