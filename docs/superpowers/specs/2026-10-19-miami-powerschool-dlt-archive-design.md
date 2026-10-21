# Miami PowerSchool dlt archive

Refs #5409. One PR, linked to #5409, closes it on merge.

## Why

Miami left PowerSchool for Focus. `kippmiami_powerschool` is a frozen BigQuery
archive that kipptaf reads for Miami's pre-Focus history. Today the only way to
rebuild it is from the `src_powerschool__*` Avro externals of the final ODBC
pull (2026-07-01). The ODBC ingestion is gone, so a correction made on the
PowerSchool server can never reach the archive.

The server still exists. #5409 needs exactly such a correction: school
30200801's AY2018 Q4 `lastday` was 2019-06-11, short of the year's 2019-06-28,
which leaves 511 attendance days with no quarter. The server now reads
2019-06-28 (verified 2026-10-19 by querying `terms` over the SSH tunnel).

The goal is a repeatable path, the same one Camden, Newark and Paterson use: dlt
loads PowerSchool tables into `dagster_kippmiami_dlt_powerschool`, and the
archive rebuilds from those tables through the package's dlt staging variant.
This PR makes the first, "final archival" pull and fixes #5409 with it.

## Goals

- Miami dlt PowerSchool assets in Dagster+, built from the shared
  `build_powerschool_dlt_assets` factory, off by default.
- A full dlt pull of every table behind the archive's 58 staging models into
  `dagster_kippmiami_dlt_powerschool`.
- The whole archive rebuilt from dlt: every staging model in the archive comes
  from the dlt variant. No archive table stays on the ODBC path.
- A per-table comparison of the old archive against the dlt rebuild, with every
  difference explained.
- #5409's step-3 count returns 0.

## Non-goals

- No sensor or schedule for Miami. The assets run only when launched by hand.
- No new archive tables or columns. The rebuild produces the same table set the
  archive has today.
- No changes to how Camden, Newark or Paterson build.
- The old `src_powerschool__*` externals and the GCS Avro files under
  `gs://teamster-kippmiami/dagster/kippmiami/powerschool/` stay in place.
  Nothing reads them after this PR, and nothing drops them.

## Anti-goals

- An unexplained difference between the old and new archive. Differences are
  fine; each needs a stated cause.
- PII values in the PR, commits or comments. The comparison posts counts and
  column names only.
- Any NJ region's dbt build breaking because of new package models.

## Decided (by the user)

- **dlt, not a one-off patch.** The archive is rebuilt from a dlt pull, not by
  hand-patching the archived date.
- **All of the frozen data uses one method.** All 58 staging tables come from
  dlt, including the 12 that today exist only as ODBC models.
- **Differences outside the 3 Q4 days are acceptable** as long as each one is
  visible and explained.
- **The load runs in Dagster+**, like the other regions, not from a codespace.
- **The fix loop** for future archive corrections: turn the Miami PowerSchool
  dlt config on, materialize the tables, rebuild the archive with dbt, turn it
  off.
- **One PR**, in this order: permanent code; turn on and load; rebuild; compare;
  turn off; merge.
- **The archive shows the server as it is at pull time**, not pinned to the
  2026-07-01 cutover. Every later fix pulls in whatever changed since the last
  pull. The guard is the stop-and-decide rule in part 4.

## What the server looks like (measured 2026-10-19)

- Rows changed since 2026-07-01 (`transaction_date` or `whenmodified`):
  `students` 1,118 of 3,946; `terms` 1 (the #5409 fix); `studentcontactassoc` 1;
  0 in `schools`, `sections`, `cc`, `attendance`, `storedgrades`,
  `pgfinalgrades`, `termbins`, `courses`, `assignmentscore`,
  `assignmentsection`, `assignmentcategoryassoc`, `person`. `reenrollments`,
  `spenrollments`, `calendar_day` and `log` have no change column, so their
  drift is unknown until the comparison.
- The old ODBC pull loaded `attendance`, `storedgrades`, `pgfinalgrades` and the
  3 assignment tables from 2018-07-01 on. The server has 0 rows before that date
  or with a null date in those tables, so the full dlt pull adds no older
  history.
- The old archive accumulated snapshots, so it can hold rows since deleted on
  the server. A dlt `replace` pull will not have them.

## The parts

### 1. Miami dlt assets (permanent)

- `src/teamster/code_locations/kippmiami/powerschool/sis/dlt/` mirroring the
  Camden layout: `assets.py` and `config/assets.yaml`. No `sensors.py` or
  `schedules.py`.
- `assets.yaml` lists every PowerSchool table the archive's 58 staging models
  read, with a `cursor_column` per table (the factory requires it; the probe
  uses it only for change detection). Take `cursor_column` values from Newark's
  config where the table exists there; for the 12 new tables, check the Oracle
  columns on the Miami server.
- Credentials: two `OnePasswordItem`s in `.k8s/1password/items.yaml`
  (`op-ps-db-kippmiami`, `op-ps-ssh-kippmiami`, pointing at the existing
  `PowerSchool DB - Miami` / `PowerSchool SSH - Miami` vault items; confirm the
  exact item names), and the `PS_DB_*` / `PS_SSH_*` variables in BOTH
  `dagster-cloud.yaml` blocks for kippmiami (`container_context` and
  `run_k8s_config`), matching Camden's. Applying `.k8s` is the user's step.
- Resources `ssh_powerschool` and `db_powerschool` from `core/resources.py`'s
  factories, added to kippmiami's `definitions.py`.
- The `dlt_powerschool_kippmiami` pool must be set to limit 1 in Dagster+, like
  the other regions.
- **First, prove the cluster can reach the server.** The 2026-10-19 checks ran
  from a codespace, not GKE. Before building on the assets, load one small table
  (`schools`) from the branch deployment. If the cluster cannot reach the
  server, stop and tell the user; an allowlist or key change would come first.

**Builder's call, off vs on:** the assets module stays in the repo permanently.
"Off" means kippmiami's `definitions.py` does not load the PowerSchool assets;
"on" means it does. Pick the smallest toggle that keeps the resources and
`dagster-cloud.yaml` wiring in place either way, and document it in
`src/teamster/code_locations/kippmiami/CLAUDE.md`.

### 2. dlt staging for the 12 ODBC-only tables (permanent)

The archive has 58 `stg_powerschool__*` tables. 46 have a dlt model in
`src/dbt/powerschool/models/sis/staging/dlt/`. These 12 do not:

`codeset`, `emailaddress`, `originalcontactmap`, `person`, `personaddress`,
`personaddressassoc`, `personemailaddressassoc`, `personphonenumberassoc`,
`phonenumber`, `prefs`, `studentcontactassoc`, `studentcontactdetail`.

- Write each as its ODBC sibling minus the struct unwrap, per _dlt staging
  variant_ in `src/dbt/powerschool/CLAUDE.md`. Check landed types in the dlt
  tables rather than assuming.
- Add the 12 to the dlt `sources-bigquery.yml`.
- **Off by default in the package** (`+enabled: false` in the package's
  `dbt_project.yml`), so Camden, Newark and Paterson are unaffected. kippmiami
  turns them on during a rebuild.
- Carry over the ODBC versions' `contains_pii` tags and tests.

### 3. The archive rebuild recipe (temporary, on during the rebuild)

Restore the `powerschool:` block in `src/dbt/kippmiami/dbt_project.yml` and the
package in `packages.yml`, as in commit `00bd5eaad7`, with these changes:

- `dlt: +enabled: true`, `odbc: +enabled: false` (the reverse of last time).
- The 12 new dlt models enabled.
- The same 16 post-hooks: the 8400 prefix on `student_number`
  (`stg_powerschool__students`), `delete ... where yearid > 35` on the 14 listed
  staging models, and `date_value >= '2026-07-01'` on
  `stg_powerschool__calendar_day`.
- The same disables, translated to whatever dlt models exist, so the rebuilt
  table set equals today's archive table set.

### 4. Compare, then rebuild prod

Build the dlt version into the dev schema first (`--target dev`), so prod stays
untouched until the comparison is accepted.

- For every table in `kippmiami_powerschool`: row count old vs new, and per
  column the count of rows whose value differs on the table's key.
- Classify each difference: type cast, float epsilon, a server-side change after
  2026-07-01, a row deleted on the server, the #5409 fix, or other. "Other"
  needs investigating before prod.
- Break the `students` changes down by column, and do the same for any table
  without a change column that shows drift.
- **Stop and decide:** if any difference would change what kipptaf reports for
  past Miami years (enrollment counts, exits, attendance or ADA, grades or GPA),
  stop before the prod build and bring it to the user with the numbers. Ordinary
  corrections that change nothing kipptaf reports go through.
- Post the result in the PR as counts and column names only.
- Then the user runs the prod build in their terminal.

### 5. Downstream and close-out

- kipptaf reads the archive as BQ-native sources, so its models may not rebuild
  on their own. Confirm whether `int_students__attendance_daily` and the other
  consumers of the 17 archive sources need a manual materialization, and do it.
- Re-run #5409's step 3: the count of attendance days after the Q4 end for
  school 30200801, AY2018, must be 0. No other school-year's quarter boundaries
  change.
- Remove the package and the `powerschool:` block again, turn the assets off,
  and merge.
- Update `src/dbt/kippmiami/CLAUDE.md` and `src/dbt/powerschool/CLAUDE.md`: the
  archive now rebuilds from dlt, and the fix loop above is the recipe.

## Constraints

- The dlt dataset is not branch-isolated: a branch-deployment run writes the
  prod `dagster_kippmiami_dlt_powerschool`. Here that is the intent, so the load
  can run from this PR's branch deployment.
- `replace` write disposition never changes an existing column's type or mode.
  The dataset is new, so this matters only on a later reload.
- `--target prod` dbt runs and all warehouse DDL go to the user's terminal.
- The new dataset holds Miami student and family PII and must never be dropped.

## Left to the builder

- The exact on/off toggle (part 1).
- The comparison's key per table and how the diff query is written.
- Whether to load the tables in one run or batches.
