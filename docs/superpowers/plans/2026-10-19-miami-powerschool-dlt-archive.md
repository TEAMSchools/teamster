# Miami PowerSchool dlt archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Miami off-by-default dlt PowerSchool assets, load the full
archive table set from the still-running server, rebuild `kippmiami_powerschool`
from dlt, and close #5409.

**Architecture:** Miami reuses `build_powerschool_dlt_assets` with its own
`assets.yaml` and no triggers. The PowerSchool dbt package gains 12 dlt staging
models, off by default. A temporary `powerschool:` block in kippmiami builds the
dlt variant into dev, a comparison against prod gates the user's prod build, and
the block is removed before merge.

**Tech Stack:** Dagster+ (GKE, k8s_job_executor), dlt over an SSH tunnel to
Oracle, dbt-bigquery, 1Password operator.

**Spec:**
`docs/superpowers/specs/2026-10-19-miami-powerschool-dlt-archive-design.md`

## Global Constraints

- One PR on `cbini/feat/claude-miami-powerschool-dlt-archive`, linked to #5409;
  it closes #5409 on merge.
- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/feat/claude-miami-powerschool-dlt-archive`.
  Use absolute paths and `git -C <worktree>` on every call; `uv run` for every
  `python`/`dbt`/`dagster`.
- No sensor or schedule for Miami PowerSchool. Assets run only by hand.
- The rebuilt archive table set equals today's, except the 2 retired package
  models below, which stay frozen.
- Post-hooks, verbatim from commit `00bd5eaad7`: `stg_powerschool__students`
  `update {{ this }} set student_number = student_number + 8400000000 where true`;
  `delete from {{ this }} where yearid > 35` on `assignmentcategoryassoc`,
  `assignmentsection`, `attendance`, `attendance_code`, `cc`, `fte`, `gen`,
  `gradecalculationtype`, `gradeformulaset`, `gradeschoolconfig`, `prefs`,
  `storedgrades`, `termbins`, `terms`; `stg_powerschool__calendar_day`
  `delete from {{ this }} where date_value >= '2026-07-01'`.
- No PII values in commits, PR body or comments: counts and column names only.
- `--target prod` dbt runs, `.k8s` applies, Dagster+ pool settings, and all
  warehouse DDL are the user's steps. Hand them over; do not run them.
- `dagster_kippmiami_dlt_powerschool` is not branch-isolated. A branch
  deployment run writes the prod dataset; that is intended here.
- Never drop `kippmiami_powerschool`, `dagster_kippmiami_dlt_powerschool`, the
  `src_powerschool__*` externals or the GCS Avro files.

## Table set

The archive has 58 `stg_powerschool__*` tables and 43 `base_`/`int_` tables
(`kippmiami_powerschool`, queried 2026-10-19). Load these 58 dlt tables:

- **45 with an existing package dlt model:** `assignmentcategoryassoc`
  `assignmentscore` `assignmentsection` `attendance` `attendance_code`
  `attendance_conversion_items` `bell_schedule` `calendar_day` `cc` `courses`
  `cycle_day` `districtteachercategory` `fte` `gen` `gradecalcformulaweight`
  `gradecalcschoolassoc` `gradecalculationtype` `gradeformulaset`
  `gradescaleitem` `gradeschoolconfig` `gradeschoolformulaassoc`
  `gradesectionconfig` `log` `pgfinalgrades` `reenrollments` `roledef` `schools`
  `schoolstaff` `sections` `sectionteacher` `spenrollments` `storedgrades`
  `studentcorefields` `students` `studenttest` `studenttestscore`
  `teachercategory` `termbins` `terms` `test` `testscore` `u_clg_et_stu`
  `u_clg_et_stu_alt` `users` `userscorefields`. Cursor columns: copy each from
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml`.
- **12 needing a new package dlt model:** `codeset` `emailaddress`
  `originalcontactmap` `person` `personaddress` `personaddressassoc`
  `personemailaddressassoc` `personphonenumberassoc` `phonenumber` `prefs`
  `studentcontactassoc` `studentcontactdetail`.
- **1 district-level:** `u_studentsuserfields`. Its archive table came from a
  kippmiami model deleted in `223c10eb60`; cursor `whenmodified` (Newark).

45 + 12 + 1 = 58, one dlt table per archive staging table. The spec's "46 have a
dlt model" counted `u_studentsuserfields`, which is a district model, not a
package one.

Frozen, not rebuilt: `int_powerschool__student_contacts` and
`int_powerschool__student_contacts_pivot`. The package disables both in their
properties YAML (retired in `06f780155b`), and a model-level `enabled: false`
beats a root-project config, so kippmiami cannot turn them on. Nothing reads
them.

## Review Focus

1. A new package model enabled in an NJ region breaks its build. Expected: none
   of the 12 resolve in kippnewark, kippcamden or kipppaterson. Test in Task 4.
2. A table that is empty on the Miami server lands no BigQuery table, so its
   staging model fails at build. Expected: every one of the 58 tables exists in
   `dagster_kippmiami_dlt_powerschool` after the load. Check in Task 3.
3. Oracle DATE columns land `TIMESTAMP` and break a staging contract. Expected:
   every staging model builds with its contract enforced. Covered by Task 5's
   dev build.
4. A post-hook silently misses its target under the dlt variant. Expected: 0
   rows with `yearid > 35` in the 14 tables, 0 `calendar_day` rows on or after
   2026-07-01, and every `student_number` >= 8400000000. Check in Task 5.
5. "Off" leaves the code location unloadable. Expected: the branch deployment
   loads kippmiami cleanly after the final off commit. Check in Task 8.

---

### Task 1: Miami dlt assets, off by default

**Files:**

- Create: `src/teamster/code_locations/kippmiami/powerschool/__init__.py`,
  `.../powerschool/sis/__init__.py`, `.../powerschool/sis/dlt/__init__.py`,
  `.../powerschool/sis/dlt/assets.py`,
  `.../powerschool/sis/dlt/config/assets.yaml`
- Modify: `src/teamster/code_locations/kippmiami/definitions.py`
- Test: `tests/libraries/test_dlt_powerschool_kippmiami_assets.py`

**Interfaces:**

- Produces: module `teamster.code_locations.kippmiami.powerschool` exporting
  `assets` (from `sis.dlt.assets`), and `config_file: pathlib.Path` in
  `sis.dlt.assets`. Asset keys `kippmiami/powerschool/sis/<table_name>`; op
  `kippmiami__powerschool`; pool `dlt_powerschool_kippmiami`.
- `assets.yaml` entries carry only `table_name` and `cursor_column` (no
  `intraday`/`nightly`: there are no triggers).
- The on/off toggle: `powerschool` present in `load_assets_from_modules` modules
  list = on; absent = off. Resources `db_powerschool`
  (`get_powerschool_oracle_resource()`) and `ssh_powerschool`
  (`get_powerschool_ssh_resource()`) are always in `resources`.

- [ ] **Step 1: Write the failing tests**

```python
def test_miami_assets_cover_exactly_the_archive_tables():
    from teamster.code_locations.kippmiami.powerschool.sis.dlt.assets import assets
    keys = {k.to_user_string() for a in assets for k in a.keys}
    assert keys == {f"kippmiami/powerschool/sis/{t}" for t in ARCHIVE_TABLES}
    assert len(keys) == 58

def test_miami_assets_op_and_pool():
    ...
    assert assets[0].op.name == "kippmiami__powerschool"
    assert assets[0].op.pool == "dlt_powerschool_kippmiami"

def test_miami_has_no_powerschool_triggers():
    # no schedules.py / sensors.py in the package
    import importlib.util
    assert importlib.util.find_spec(
        "teamster.code_locations.kippmiami.powerschool.sis.dlt.sensors") is None
    assert importlib.util.find_spec(
        "teamster.code_locations.kippmiami.powerschool.sis.dlt.schedules") is None
```

`ARCHIVE_TABLES` is a module constant in the test holding the 58 names from
_Table set_.

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError`):
      `uv run pytest tests/libraries/test_dlt_powerschool_kippmiami_assets.py -q`
- [ ] **Step 3: Get the 12 new tables' cursor columns from the server.** Write a
      throwaway `tests/test_zz_miami_cursor_cols.py` that opens the tunnel with
      the `_KIPPMIAMI`-suffixed credentials (same `build_resources` shape as the
      2026-10-19 probe) and reads `all_tab_columns` for each table. Rule:
      `whenmodified` if present, else `transaction_date`, else `null`. Run with
      `-s --tb=short`, record, delete the file.
- [ ] **Step 4: Implement** the module mirroring
      `kippcamden/powerschool/sis/dlt/assets.py` without schedules or sensors,
      the 58-entry `assets.yaml`, and add the two resources plus the imports to
      `definitions.py` with `powerschool` NOT in the modules list.
- [ ] **Step 5: Run, expect PASS.** Also
      `uv run python -m py_compile src/teamster/code_locations/kippmiami/definitions.py`.
      (Importing `kippmiami.definitions` fails in the codespace on `FOCUS_DB`;
      that is expected, per `src/teamster/CLAUDE.md`.)
- [ ] **Step 6: Commit**
      `feat(kippmiami): add off-by-default PowerSchool dlt assets`.

### Task 2: Miami PowerSchool credentials in the cluster

**Files:**

- Modify: `.k8s/1password/items.yaml`,
  `src/teamster/code_locations/kippmiami/dagster-cloud.yaml`

**Interfaces:**

- Produces: k8s secrets `op-ps-db-kippmiami` (keys `server`, `database`, `port`,
  `username`, `password`) and `op-ps-ssh-kippmiami` (keys `host`, `port`,
  `username`, `password`, plus the remote-bind key Camden uses). Copy key names
  from Camden's `dagster-cloud.yaml`, do not guess.

- [ ] **Step 1: Ask the user for the exact 1Password item names** for the Miami
      PowerSchool DB and SSH items in the `Data Team` vault. Do not guess
      `PowerSchool DB - Miami`.
- [ ] **Step 2: Add two `OnePasswordItem`s** after the Camden pair, same shape.
- [ ] **Step 3: Add the 10 `PS_*` variables** (`PS_DB_HOST`, `PS_DB_DATABASE`,
      `PS_DB_PORT`, `PS_DB_USERNAME`, `PS_DB_PASSWORD`, `PS_SSH_HOST`,
      `PS_SSH_PORT`, `PS_SSH_USERNAME`, `PS_SSH_PASSWORD`,
      `PS_SSH_REMOTE_BIND_HOST`) to BOTH the `container_context` and the
      `run_k8s_config` blocks, matching Camden's secret refs with `kippmiami`.
- [ ] **Step 4: Verify** each block has all 10:
      `rg -c 'name: PS_' src/teamster/code_locations/kippmiami/dagster-cloud.yaml`
      → 20.
- [ ] **Step 5: Commit** `feat(kippmiami): wire PowerSchool credentials`.
- [ ] **Step 6: Hand the user** the `.k8s` apply for the two new items and the
      Dagster+ pool setting `dlt_powerschool_kippmiami` = 1. Wait for both.

### Task 3: Prove the cluster path, then load all 58 tables

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/definitions.py` (toggle on)

- [ ] **Step 1: Turn on**: add `powerschool` to the modules list. Commit
      `chore(kippmiami): turn on PowerSchool dlt assets for the archive pull`.
- [ ] **Step 2: Push and open the PR** non-draft (body from
      `.github/pull_request_template.md`, `Closes #5409`), so the branch
      deployment builds. Wait for the kippmiami location to load.
- [ ] **Step 3: Gate**: launch `kippmiami/powerschool/sis/schools` alone in the
      branch deployment with `mcp__dagster-plus__launch_asset_run`. Expected:
      success and a `schools` table with 5 rows in
      `dagster_kippmiami_dlt_powerschool`. On an SSH or connect failure, stop
      and tell the user; nothing below proceeds.
- [ ] **Step 4: Full load**: one run of all 58 assets (one `launch_asset_run`
      with the whole selection, not per-table runs).
- [ ] **Step 5: Verify** with `INFORMATION_SCHEMA.TABLES` that all 58 tables
      exist, and that row counts match the 2026-10-19 server counts where known
      (`students` 3,946, `cc` 98,865, `attendance` 497,065, `storedgrades`
      239,545, `pgfinalgrades` 747,533, `terms` 214, `assignmentscore`
      2,510,188). A missing table (empty on the server) gets noted for Task 5.

### Task 4: 12 dlt staging models, off by default

**Files:**

- Create: `src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__<t>.sql`
  for the 12 tables, and their properties YAML beside the dlt models' existing
  properties.
- Modify: `src/dbt/powerschool/models/sis/staging/dlt/sources-bigquery.yml`,
  `src/dbt/powerschool/dbt_project.yml`

**Interfaces:**

- Produces: 12 models with the same names, columns and contract types as their
  ODBC siblings, disabled in the package `dbt_project.yml` under
  `sis: staging: dlt:` one key per model.
- Read `src/dbt/powerschool/CLAUDE.md` _dlt staging variant_ and invoke
  `dbt-local-dev` before any build.

- [ ] **Step 1: Write the NJ guard check** and run it, expect it to print
      nothing for each of kippnewark, kippcamden, kipppaterson:
      `uv run dbt ls --project-dir src/dbt/<district> --resource-type model --select stg_powerschool__person stg_powerschool__codeset ... (all 12)`.
      It passes now (models do not exist) and must still pass after Step 3.
- [ ] **Step 2: Read each landed table's column types** from
      `dagster_kippmiami_dlt_powerschool.INFORMATION_SCHEMA.COLUMNS`.
- [ ] **Step 3: Write the 12 models** from their ODBC siblings, dropping the
      struct unwrap and the `_file_name` dedup, casting to contract types. Add
      the 12 source entries (asset key
      `["{{ project_name }}", powerschool, sis, <t>]`) and the 12 package
      disables. Copy `contains_pii` tags and tests from the ODBC properties.
- [ ] **Step 4: Re-run Step 1** in all three NJ districts: still empty.
- [ ] **Step 5: Commit**
      `feat(powerschool): add dlt staging for the 12 ODBC-only tables`.

### Task 5: Rebuild recipe and dev build

**Files:**

- Modify: `src/dbt/kippmiami/dbt_project.yml`, `src/dbt/kippmiami/packages.yml`,
  `src/dbt/kippmiami/package-lock.yml`
- Create (temporary):
  `src/dbt/kippmiami/models/powerschool/sis/staging/stg_powerschool__u_studentsuserfields.sql`
  and its properties YAML, from `223c10eb60^`, rewritten for
  `source("powerschool_dlt", "u_studentsuserfields")`: drop `.int_value`, keep
  `safe_cast(c_504_status as int)`,
  `if(is_gifted = 1, 'Y', 'N') as gifted_and_talented`, and `is_504`.

- [ ] **Step 1: Restore the `powerschool:` block** from `00bd5eaad7` with
      `dlt: +enabled: true`, `odbc: +enabled: false`, the 12 new models enabled,
      and the post-hooks from _Global Constraints_ moved under `dlt:`. Add
      `- local: ../powerschool` to `packages.yml`; `uv run dbt deps`.
- [ ] **Step 2: Match the table set.** Compare
      `uv run dbt ls --project-dir src/dbt/kippmiami --resource-type model --select package:powerschool stg_powerschool__u_studentsuserfields --output name`
      with the archive's 101 tables minus the 2 frozen contact models. Disable
      every extra; any missing one is a stop-and-ask.
- [ ] **Step 3: Build into dev**:
      `uv run dbt build --project-dir src/dbt/kippmiami --target dev` with the
      Step 2 selection. Expected: every model builds and every `severity: error`
      test passes. Note the dev dataset name.
- [ ] **Step 4: Check the hooks** (Review Focus 4) against the dev tables.
- [ ] **Step 5: Commit**
      `chore(kippmiami): re-include the powerschool package for the dlt archive rebuild`.

### Task 6: Compare dev against the prod archive

**Files:** none committed. Scripts live in the session scratchpad.

- [ ] **Step 1: Per table**, row counts dev vs prod, and per column the count of
      rows whose value differs, joined on the table's uniqueness-test key from
      its properties YAML. Rows only in prod and rows only in dev are counted
      separately.
- [ ] **Step 2: Classify** every nonzero cell: type cast, float epsilon (<
      1e-10), server change after 2026-07-01, row deleted on the server, the
      #5409 fix, or other. Break `students` down by column.
- [ ] **Step 3: Stop and decide.** If any difference would change what kipptaf
      reports for past Miami years (enrollment counts, exits, attendance or ADA,
      grades or GPA), bring it to the user with the numbers and wait. Any
      "other" also stops.
- [ ] **Step 4: Post** the table to the PR as counts and column names only.

### Task 7: Prod build, downstream, and the #5409 check

- [ ] **Step 1: Hand the user** the prod build: same selection as Task 5 Step 3,
      `--target prod`, run from the worktree.
- [ ] **Step 2: Verify prod** matches dev counts for every table.
- [ ] **Step 3: Downstream.** List kipptaf models reading the archive:
      `uv run dbt ls --project-dir src/dbt/kipptaf --resource-type model --select source:kippmiami_powerschool+`.
      Ask the user to launch them in Dagster as one run.
- [ ] **Step 4: #5409 step 3**: count
      `kipptaf_students.int_students__attendance_daily` rows for school
      30200801, AY2018, with `calendardate` after 2019-06-11 and a null `term`.
      Expected: 0. Also confirm no other school-year's Q4 `lastday` moved, by
      comparing `stg_powerschool__terms` dev vs the pre-rebuild Task 6 snapshot:
      only id 2804 differs.

### Task 8: Turn off, document, merge-ready

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/definitions.py`,
  `src/dbt/kippmiami/dbt_project.yml`, `packages.yml`, `package-lock.yml`,
  `src/dbt/kippmiami/CLAUDE.md`, `src/dbt/powerschool/CLAUDE.md`,
  `src/teamster/code_locations/kippmiami/CLAUDE.md`
- Delete: the temporary `stg_powerschool__u_studentsuserfields` model and YAML.

- [ ] **Step 1: Turn off**: remove `powerschool` from the modules list; remove
      the `powerschool:` block, the package entry and the temporary model;
      `uv run dbt deps`.
- [ ] **Step 2: Document** the fix loop and the toggle in the three CLAUDE.md
      files: the archive now rebuilds from dlt; the recipe is in this PR's Task
      5 commit; the 2 contact intermediates stay frozen and why.
- [ ] **Step 3: Lint**:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`.
- [ ] **Step 4: Commit and push**; confirm the branch deployment loads kippmiami
      cleanly with the assets off (Review Focus 5), and CI is green.
