# NJ 504 flag from the PowerSchool state field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the NJ branch of `is_504` read PowerSchool's state field
`PID_504_TF` in every school year, and give schools a one-time worklist to
correct PowerSchool records.

**Architecture:** PR 1 adds a boolean `is_504` to the `powerschool` package
model `stg_powerschool__s_nj_stu_x`. After Dagster rebuilds it in all 3 NJ
districts, PR 2 swaps `suf.is_504` for `njs.is_504` in kipptaf
`int_students__student_enrollments`. The worklist is a Google Sheet built from a
scratchpad script, outside the repo.

**Tech Stack:** dbt (BigQuery), Dagster+, BigQuery MCP, Google Drive and Sheets
MCP, Python with pandas for the worklist.

**Spec:** `docs/superpowers/specs/2026-11-10-nj-504-state-field-design.md`
(issue #6354)

## Global Constraints

- Package derivation, verbatim: `if(pid_504_tf = 1, true, false) as is_504`.
- kipptaf NJ branch, verbatim: `coalesce(njr.pid_504_tf, njs.is_504, false)`.
  The Miami branch (`ar.is_504`) does not change.
- Expected flagged enrollment rows after PR 2 (from the spec, measured
  2026-11-10; school fixes between then and the build move these by a few):

  | Region   | School years       | Today | After |
  | -------- | ------------------ | ----: | ----: |
  | Newark   | 2026–27            |    83 |    86 |
  | Camden   | 2026–27            |    46 |    48 |
  | Paterson | 2026–27            |     0 |    11 |
  | Newark   | 2021–22 to 2025–26 |   724 |   702 |
  | Camden   | 2021–22 to 2025–26 |   268 |   260 |
  | Paterson | 2021–22 to 2025–26 |    11 |    11 |
  | Newark   | before 2021–22     |   791 |   709 |
  | Camden   | before 2021–22     |   154 |   135 |

- No student-level values in the repo, a commit, a PR, an issue, or a comment.
  Outbound counts are region-level aggregates with no cell under 10.
- Work in the worktree by absolute path: `git -C <worktree>`, `uv run`, and
  `--project-dir <worktree>/src/dbt/<project>`.
- Invoke the `dbt-local-dev` skill before the first local dbt command, and use
  its dev target, `--defer`, and `--state` flags on every build below.
- Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree before each push.
- Shared staging writes (`--target staging`) need the user's go-ahead in the
  turn just before, each in its own Bash call.
- PR bodies follow `.github/pull_request_template.md`. PR 1 says `Refs #6354`.
  PR 2's branch links to #6354, and its body says `Closes #6354`.

## Review Focus

1. **A district rebuilds late.** If PR 2 merges before all 3 district prod
   tables carry `is_504`, the kipptaf union null-fills the column and every NJ
   current-year flag reads false. PR 2 must not merge until Task 2's check
   passes. Task 4 Step 1 re-runs that check.
2. **`PID_504_TF` never touched.** The field defaults to No, so a null reads
   false, never null. Task 1 Step 4 asserts 0 nulls.
3. **Past enrollment with no `S_NJ_REN_X` row.** These rows, mostly before
   2021–22, must fall back to `S_NJ_STU_X`, not to false. Task 4 Step 6 checks
   the "before 2021–22" rows: Newark 709 and Camden 135, not the lower counts
   that false would give.
4. **Miami.** Its values, nulls included, must not move. Task 4 Step 6 compares
   Miami's true and null counts by year against prod.
5. **Grain.** The change swaps a column from a join that already exists, so the
   row count must equal prod. Task 4 Step 6 checks it. The worklist keeps one
   row per student even when a student is in 2 groups (Task 3 Step 3).

---

### Task 1: Add `is_504` to the package staging model (PR 1)

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__s_nj_stu_x.sql:435`
  (append after the last `cast(...)` line, before `from`)
- Modify:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__s_nj_stu_x.yml:719-720`
  (new entry after `pid_504_tf`)

**Interfaces:**

- Produces: column `is_504` (`boolean`, never null) on
  `stg_powerschool__s_nj_stu_x` in `kippnewark`, `kippcamden`, and
  `kipppaterson`. Task 2 and Task 4 read it.

- [ ] **Step 1: Declare the column in the contract first**

  Add after the `pid_504_tf` entry:

  ```yaml
  - name: is_504
    data_type: boolean
    description: <see below>
    config:
      meta:
        contains_pii: true
  ```

  The description says: true when `pid_504_tf` is 1, the "Section 504" field on
  the PowerSchool NJ SLA page; false when it is 0 or unset, because the field
  defaults to No.

- [ ] **Step 2: Run the build to see the contract fail**

  Run `uv run dbt deps --project-dir <worktree>/src/dbt/kippnewark` in its own
  Bash call, then
  `uv run dbt build --select stg_powerschool__s_nj_stu_x --project-dir <worktree>/src/dbt/kippnewark`
  with the `dbt-local-dev` dev flags. Expected: FAIL, contract error listing
  `is_504` as missing in the definition.

- [ ] **Step 3: Add the derivation**

  Append `if(pid_504_tf = 1, true, false) as is_504,` after
  `cast(sid_excludeenrollment as int) as sid_excludeenrollment,`. It goes last
  because it is a logical, after the casts (S6, S7). Leave the disabled odbc and
  sftp variants alone.

- [ ] **Step 4: Rebuild and check the values**

  Rerun the Step 2 build. Expected: PASS, including the `studentsdcid` unique
  test. Then query the dev relation dbt reports:

  ```sql
  select
      count(*) as n_rows,
      countif(is_504 is null) as n_null,
      countif(is_504 != coalesce(pid_504_tf = 1, false)) as n_mismatch,
      countif(is_504) as n_true,
  from <dev relation>
  ```

  Expected: `n_null` = 0, `n_mismatch` = 0, and `n_true` equals
  `countif(pid_504_tf = 1)` on prod
  `kippnewark_powerschool.stg_powerschool__s_nj_stu_x`.

- [ ] **Step 5: Repeat Steps 2 and 4 for `kippcamden` and `kipppaterson`**

  Run `dbt deps` in each project first. Expected: both builds pass, and both
  queries return the same 3 results as Step 4.

- [ ] **Step 6: Lint**

  Run trunk check on the `.sql` and `.yml`. Expected: no issues.

- [ ] **Step 7: Commit and push**

  ```bash
  git -C <worktree> add src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__s_nj_stu_x.sql src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__s_nj_stu_x.yml
  git -C <worktree> commit -m "feat(powerschool): add is_504 to stg_powerschool__s_nj_stu_x"
  git -C <worktree> push
  ```

- [ ] **Step 8: Turn PR #6355 into PR 1**

  Retitle #6355 `feat(powerschool): add is_504 to stg_powerschool__s_nj_stu_x`
  and rewrite its body from the template. Say that it now carries the spec, the
  plan, and the package column; keep `Refs #6354`; and tick the dbt checklist.
  Expected: Trunk passes, and dbt Cloud CI passes or finds nothing modified to
  build.

### Task 2: Confirm the column reached prod in all 3 districts

**Interfaces:**

- Consumes: PR 1 merged and deployed.
- Produces: the precondition Task 4 needs. `is_504` exists on all 3 district
  prod tables and on the kipptaf union view.

- [ ] **Step 1: Check the column after the deploy**

  ```sql
  select table_schema, data_type
  from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.COLUMNS
  where table_name = 'stg_powerschool__s_nj_stu_x' and column_name = 'is_504'
      and table_schema in (
          'kippnewark_powerschool', 'kippcamden_powerschool',
          'kipppaterson_powerschool', 'kipptaf_powerschool'
      )
  ```

  Expected: 4 rows, each `BOOL`.

- [ ] **Step 2: Rebuild any district that is missing it**

  For each missing district, find the asset key with
  `mcp__dagster-plus__get_assets`, then rematerialize it with
  `mcp__dagster-plus__launch_asset_run`. Rerun Step 1. If only
  `kipptaf_powerschool` is missing, launch the kipptaf
  `stg_powerschool__s_nj_stu_x` asset the same way. Expected: 4 rows.

- [ ] **Step 3: Check the values in prod**

  Run the Task 1 Step 4 query against each district's prod table. Expected:
  `n_null` = 0 and `n_mismatch` = 0.

### Task 3: Build the one-time worklist (outside the repo)

**Files:**

- Create:
  `/tmp/claude-1000/-workspaces-teamster/816b78a1-39db-4978-adc1-136bb689ca74/scratchpad/504cmp/worklist.py`
  (scratch, never committed; reuse `load.py` in the same folder)
- Output: a Google Sheet named `NJ 504 worklist <build date>` in the user's
  Drive, unshared.

**Interfaces:**

- Consumes: the raw PowerSchool fields `pid_504_tf` and `c_504_status`. It does
  not need Task 1, so it can run as soon as the user is ready.
- EdPlan inputs, Newark only:
  - Google Sheet "TEAM 504 - 20261110" (`Sheet1` and `EDPlan-504StudentReport`),
    saved as
    `/home/vscode/.claude/projects/-workspaces-teamster/816b78a1-39db-4978-adc1-136bb689ca74/tool-results/mcp-claude_ai_Google_Drive-blob-1794343092103-x99e4i.xlsx`.
  - The R100 report at
    `/workspaces/teamster/.claude/scratch/R100!njteamcharter!15-25-00-647345!11-10-26.xls`.
  - At task start, ask the user whether newer exports or a Camden export exist.

- [ ] **Step 1: Pull PowerSchool current students for all 3 regions**

  Use ADC from Python, as in `ps_pull.py`, and write to scratch CSV. The pull
  covers `enroll_status = 0` and `dcid >= 1` from each district's
  `stg_powerschool__students`, `stg_powerschool__s_nj_stu_x`, and
  `stg_powerschool__schools`, plus Newark and Camden
  `stg_powerschool__u_studentsuserfields`. Columns: `student_number`, last and
  first name, school, grade, `pid_504_tf`, `c_504_status`.

- [ ] **Step 2: Derive EdPlan status for Newark**

  Assign each student exactly one status, in this order:

  - `current plan`: in `Sheet1` with `End Date` on or after the build date.
  - `plan past end date`: in `Sheet1`, `End Date` before the build date.
  - `lapsed`: in R100, not in `Sheet1`.
  - `not eligible`: a
    `Currently Valid: Section 504 Non-Eligibility Determination` event, not in
    `Sheet1` or R100.
  - `none`: everyone else.

- [ ] **Step 3: Assign groups and assert the shape**

  Use the spec's groups 1–4. Groups 3 and 4 apply to Newark only, unless a
  Camden export arrived. A student in 2 groups gets one row listing both.
  Assert:

  - one row per region and `student_number`;
  - every row is in at least 1 group;
  - no row has `enroll_status` other than 0.

  Print counts by region and group. As a sanity check against 2026-11-10, Newark
  should be near 110 in group 3, Paterson at 11 in group 2, and every group 1
  cell under 10.

- [ ] **Step 4: Build the Summary rows**

  Add counts by region and group. Add counts of exited students whose past-year
  flag changes. Prod does not have the new values yet, so compute them with an
  ad hoc join:

  - Start from prod `kipptaf_students.int_students__student_enrollments`, with
    `enroll_status != 0` and the region not Miami.
  - Left join `kipptaf_powerschool.stg_powerschool__s_nj_ren_x` on
    `reenrollments_dcid`.
  - Left join `kipptaf_powerschool.stg_powerschool__s_nj_stu_x` on
    `students_dcid`.
  - Both joins also match on `_dbt_source_project`.
  - New value: `coalesce(njr.pid_504_tf, njs.pid_504_tf = 1, false)`. Count the
    rows where it differs from `is_504`.

- [ ] **Step 5: Write the Google Sheet**

  Invoke `anthropic-skills:google-workspace` before the first Drive or Sheets
  write. Create the spreadsheet with tabs Newark, Camden, Paterson, and Summary.
  Columns per the spec: school, grade, student number, name, `PID_504_TF`,
  `C_504_STATUS`, EdPlan status, EdPlan plan end date, group, suggested fix, and
  notes. Expected: each tab's row count read back with `get_values` equals the
  local count.

- [ ] **Step 6: Hand it off**

  Give the user the sheet link and the Summary counts in the terminal. Do not
  share the sheet. Post nothing student-level anywhere else.

### Task 4: Switch kipptaf to the state field (PR 2)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql:588-593`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml:778-783`

**Interfaces:**

- Consumes: `njs.is_504` from Task 1, with Task 2 passed.
- Produces: the new `is_504` values on `int_students__student_enrollments`.
  Column name and type do not change, so no downstream model changes.

- [ ] **Step 1: Re-check the precondition and create the branch**

  Rerun Task 2 Step 1, expecting 4 `BOOL` rows. Then:

  ```bash
  gh issue develop 6354 --name anthonygwalters/feat/claude-is-504-state-field
  git worktree add /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-is-504-state-field anthonygwalters/feat/claude-is-504-state-field
  ```

  Confirm the branch starts from current `origin/main`.

- [ ] **Step 2: Record the "before" numbers (the failing check)**

  Run this against prod `kipptaf_students.int_students__student_enrollments`:

  ```sql
  select
      region,
      case
          when academic_year = 2026 then '2026-27'
          when academic_year >= 2021 then '2021-22 to 2025-26'
          else 'before 2021-22'
      end as school_years,
      count(*) as n_rows,
      countif(is_504) as n_504,
  from <relation>
  where region != 'Miami'
  group by region, school_years
  ```

  Expected: about the "Today" column, which does not match "After".

- [ ] **Step 3: Change the expression and its comment**

  - Replace `coalesce(njr.pid_504_tf, suf.is_504, false)` with
    `coalesce(njr.pid_504_tf, njs.is_504, false)`.
  - Rewrite the comment on lines 588–590:
    - NJ reads the past-enrollment copy (`njr`, joined on `reenrollments_dcid`)
      when one exists, else the student record (`njs`).
    - Focus never populates those PowerSchool dcids, so Miami reads
      `int_focus__students.is_504`.
    - A Miami null means unset, not false.
  - Keep the `suf` join.

- [ ] **Step 4: Rewrite the `is_504` description**

  The NJ sentence says: `pid_504_tf` from `stg_powerschool__s_nj_ren_x` for a
  row from a past-enrollment record, else `is_504` from
  `stg_powerschool__s_nj_stu_x`, else false. Keep the Miami sentences as they
  are.

- [ ] **Step 5: Build in dev**

  Run `uv run dbt deps --project-dir <worktree2>/src/dbt/kipptaf`, then
  `uv run dbt build --select int_students__student_enrollments --project-dir <worktree2>/src/dbt/kipptaf`
  with the `dbt-local-dev` flags. Expected: PASS, including the model's
  uniqueness test.

- [ ] **Step 6: Run the verification queries on the dev relation**

  - Rerun the Step 2 query. Expected: the "After" column, plus or minus records
    schools fixed since 2026-11-10.
  - Compare total `count(*)` with prod. Expected: equal.
  - Compare Miami `countif(is_504)` and `countif(is_504 is null)` by
    `academic_year` with prod. Expected: identical.

- [ ] **Step 7: Lint, commit, push**

  Run trunk check on both files, then `git -C <worktree2> add <both files>` and
  `git -C <worktree2> commit -m "feat(dbt): read the NJ 504 flag from the PowerSchool state field"`,
  then push.

- [ ] **Step 8: Refresh the district staging copies**

  Ask the user's go-ahead first. Then, one Bash call per district:

  ```bash
  uv run dbt clone --select stg_powerschool__s_nj_stu_x --target staging --state /workspaces/teamster/src/dbt/<district>/target/prod --full-refresh --project-dir <worktree2>/src/dbt/<district>
  ```

  Expected: each `zz_stg_<district>_powerschool.stg_powerschool__s_nj_stu_x`
  carries `is_504`.

- [ ] **Step 9: Open PR 2**

  Use the template:

  - Summary: what changes and why.
  - Reviewer Notes: the expected-effect table, the history change, and that CI
    rebuilds a large graph.
  - `Closes #6354`, and a mention of #6284.

  Offer to watch CI. Expected: dbt Cloud CI passes. Rerun the Step 2 query
  against the CI schema (`dbt_cloud_pr_<job>_<pr>_kipptaf_students`) and match
  the "After" column. If CI fails with `is_504` not found, invoke `pr-ci-review`
  and diagnose which copy is stale.

### Task 5: Verify in prod after PR 2 merges

**Interfaces:**

- Consumes: PR 2 merged, and Dagster rebuilt
  `int_students__student_enrollments`.

- [ ] **Step 1: Run the Task 4 Step 2 query against prod**

  Expected: the "After" column, give or take school fixes.

- [ ] **Step 2: Close out**

  - Confirm #6354 closed when PR 2 merged.
  - Post the region totals on #6354, with no cell under 10.
  - If #6284 has merged, comment there that `is_504` values changed and that its
    DDI Suite comparison needs a rerun.
