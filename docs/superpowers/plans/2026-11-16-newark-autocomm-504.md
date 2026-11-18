# Newark PowerSchool 504 Flag from EdPlan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Newark's nightly student AutoComm file gains a 21st column,
`S_NJ_STU_X.PID_504_TF`, that mirrors active EdPlan 504 plans for currently
enrolled students and writes back PowerSchool's own value for everyone else.

**Architecture:** kipptaf reads Newark's EdPlan 504 report through a new source
and `union_relations` pass-through. A rollup keeps one row per student with an
active plan. The shared kipptaf `rpt_powerschool__autocomm_students` view
computes the column for Newark rows, null for other regions. Only Newark's
wrapper selects it, last.

**Tech Stack:** dbt (BigQuery), kipptaf and kippnewark projects; Dagster
extracts unchanged.

**Spec:** `docs/superpowers/specs/2026-11-16-newark-autocomm-504-design.md`
(approved 2026-11-16, issue #6423).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-newark-autocomm-504`
  (call it `<wt>`). Use `git -C <wt>` and absolute paths. Always `uv run`.
- Newark only. The region test is the literal `'kippnewark'` on
  `_dbt_source_project`, with a one-line comment (S20).
- New column: `s_nj_stu_x__pid_504_tf`, `int64`, `contains_pii: true`. It is the
  last column of the Newark wrapper. Camden and Paterson wrappers do not change.
- Active plan: `event_selector = 'Currently Valid: Section 504 Plan'` and
  (`end_date is null` or
  `end_date >= current_date('{{ var("local_timezone") }}')`).
- Write-back rule, first match wins: region not Newark → null; Newark has no
  active plans tonight → current value; `enroll_status != 0` → current value;
  active plan → 1; else 0. Current value is
  `if(stg_powerschool__s_nj_stu_x.is_504, 1, 0)`, so a missing row gives 0.
  Never `coalesce` the EdPlan flag with the PowerSchool value.
- A Newark row never carries a blank in the new column; a blank clears the field
  in PowerSchool.
- The pass-through, the rollup, and the AutoComm model stay views, so "today" is
  evaluated when the 03:05 extract reads them.
- PII: student-level rows stay in the terminal and the session scratchpad.
  GitHub gets aggregates with no cell under 10.
- A `--target staging` write needs the user's go-ahead in the turn right before
  it, in its own Bash call, with the consent restated.

## Review Focus

1. A plan ending today (`end_date = current_date`) counts as active. Pinned by
   rollup fixture 1007 (Task 1).
2. A student with 2 active plan rows still gets 1 rollup row. Pinned by rollup
   fixture 1006 (Task 1).
3. A Newark student with no `S_NJ_STU_X` row gets 0, not null. Pinned by fixture
   2005 (Task 2).
4. An EdPlan plan for a student who is not in the file adds no row. Pinned by
   rollup row 9999 in the Task 2 fixture.
5. A night with no active plans in the EdPlan report writes back every Newark
   value. Pinned by Task 2's second unit test.

---

### Task 1: kipptaf source, pass-through, and active-plan rollup

**Files:**

- Modify: `src/dbt/kipptaf/models/edplan/sources-kippnewark.yml`
- Create:
  `src/dbt/kipptaf/models/edplan/staging/stg_edplan__section_504_student_report.sql`
- Create:
  `src/dbt/kipptaf/models/edplan/staging/properties/stg_edplan__section_504_student_report.yml`
- Create:
  `src/dbt/kipptaf/models/edplan/intermediate/int_edplan__section_504_active_plan_rollup.sql`
- Create:
  `src/dbt/kipptaf/models/edplan/intermediate/properties/int_edplan__section_504_active_plan_rollup.yml`

**Interfaces:**

- Consumes: Newark prod
  `kippnewark_edplan.stg_edplan__section_504_student_report` (`student_number`
  int64, `event_selector` string, `end_date` date).
- Produces: `int_edplan__section_504_active_plan_rollup`, a view with columns
  `student_number` (int64) and `_dbt_source_project` (string). One row per
  student with at least 1 active plan.

- [ ] **Step 1: Regenerate prod manifests and seed your dev copy**

Before any edit, so the manifests describe `main`. Run each line as its own
call; run `uv run dbt deps --project-dir <wt>/src/dbt/<project>` for both
projects first.

```bash
uv run dbt parse --target prod --project-dir <wt>/src/dbt/kippnewark --target-path target/prod
uv run dbt parse --target prod --project-dir <wt>/src/dbt/kipptaf --target-path target/prod
uv run dbt clone --select stg_edplan__section_504_student_report --target dev --state <wt>/src/dbt/kippnewark/target/prod --full-refresh --project-dir <wt>/src/dbt/kippnewark
```

Expected: the clone reports `PASS=1`. Your `zz_<user>_kippnewark_edplan` copy
has the same row count as prod.

- [ ] **Step 2: Write the failing unit test**

In the rollup's properties file, unit test `test_active_plan_rollup`. Input
`ref('stg_edplan__section_504_student_report')`, `format: sql`, all rows
`_dbt_source_project = 'kippnewark'`:

| student_number | event_selector                                         | end_date                           |
| -------------- | ------------------------------------------------------ | ---------------------------------- |
| 1001           | Currently Valid: Section 504 Plan                      | 2099-12-31                         |
| 1002           | Currently Valid: Section 504 Plan                      | null                               |
| 1003           | Currently Valid: Section 504 Plan                      | 2000-01-01                         |
| 1004           | Previous: Section 504 Plan                             | 2099-12-31                         |
| 1005           | Currently Valid: Section 504 Eligibility Determination | null                               |
| 1006           | Currently Valid: Section 504 Plan                      | 2099-12-31 (2 rows)                |
| 1007           | Currently Valid: Section 504 Plan                      | `current_date('America/New_York')` |

Expect `(student_number, _dbt_source_project)`: (1001, kippnewark), (1002,
kippnewark), (1006, kippnewark), (1007, kippnewark).

- [ ] **Step 3: Run it to see it fail**

Run:
`uv run dbt test --select test_active_plan_rollup --target dev --project-dir <wt>/src/dbt/kipptaf`
Expected: FAIL, because the model does not exist yet.

- [ ] **Step 4: Add the source and the pass-through**

Add table `stg_edplan__section_504_student_report` to the existing
`kippnewark_edplan` source, with `config.meta.dagster.group: edplan` and
`asset_key: [kippnewark, edplan, stg_edplan__section_504_student_report]`, the
same shape as `int_edplan__njsmart_powerschool_union` in that file. The
pass-through copies `int_edplan__njsmart_powerschool_union.sql`, with 1 relation
and the same AM04 trunk-ignore and inline `regexp_extract`. Its properties file
has a model description, a model-level `contains_pii: true`, and a
`_dbt_source_project` column description. It has no uniqueness test, because it
is a kipptaf union view.

- [ ] **Step 5: Write the rollup**

Name the active-plan rule as `is_active_504_plan` in a CTE (S10), then keep one
row per `student_number` and `_dbt_source_project` where it is true. Use the S12
annotation if you use `distinct`. Properties: the model description states it
must stay a view because the rule reads `current_date`. Add the model-level
`dbt_utils.unique_combination_of_columns` on
`[student_number, _dbt_source_project]` at `severity: error`, column
descriptions, and `contains_pii: true` on `student_number`.

- [ ] **Step 6: Build and test**

Run:
`uv run dbt build --select stg_edplan__section_504_student_report int_edplan__section_504_active_plan_rollup --target dev --defer --favor-state --state <wt>/src/dbt/kipptaf/target/prod --project-dir <wt>/src/dbt/kipptaf 2>&1 | tail -n 15`
Expected: the unit test and the grain test pass, and both views build.

- [ ] **Step 7: Check the count against prod**

BigQuery MCP: the dev rollup's Newark row count equals
`count(distinct student_number)` of active plans in prod
`kippnewark_edplan.stg_edplan__section_504_student_report`, using the same rule.
That was 135 on 2026-11-16.

- [ ] **Step 8: Lint and commit**

Run
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`
from `<wt>`, and fix any findings. Commit
`feat(dbt): kipptaf rollup of active EdPlan 504 plans` with `Refs #6423`.

### Task 2: The 504 column and write-back rule in the kipptaf AutoComm model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/powerschool/rpt_powerschool__autocomm_students.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/powerschool/properties/rpt_powerschool__autocomm_students.yml`

**Interfaces:**

- Consumes: Task 1's rollup.
  - `stg_powerschool__s_nj_stu_x`: `studentsdcid`, `_dbt_source_project`,
    `is_504` (bool).
  - `int_extracts__student_enrollments`: `students_dcid`, `enroll_status`.
- Produces: `rpt_powerschool__autocomm_students.s_nj_stu_x__pid_504_tf` (int64).
  It is 1 or 0 on every Newark row and null on other regions.

- [ ] **Step 1: Check the grain in prod**

BigQuery MCP on `kipptaf_extracts.rpt_powerschool__autocomm_students`:
`count(*)` equals
`count(distinct format('%T|%T', student_number, code_location))`. Expected:
equal, so the grain test can land at `error` (#5990).

- [ ] **Step 2: Write the failing unit tests**

Both tests use `overrides: vars: {current_academic_year: 2026}`. Enrollment rows
use `academic_year = 2026`, `rn_year = 1`, and `grade_level = 5`. List every
other model the view reads as an input with `rows: []`:
`stg_powerschool__students`, `int_powerschool__district_entry_date`,
`int_students__graduation_path_codes`, and `stg_powerschool__s_stu_x`. The
rollup input is `format: sql`, because the model is new. Every test expects
`student_number`, `code_location`, and `s_nj_stu_x__pid_504_tf`.

`test_pid_504_tf_mirrors_edplan`, with rollup rows (2001, kippnewark), (2004,
kippnewark), and (9999, kippnewark):

| student_number | region     | enroll_status | S_NJ_STU_X `is_504` | expect |
| -------------- | ---------- | ------------- | ------------------- | ------ |
| 2001           | kippnewark | 0             | false               | 1      |
| 2002           | kippnewark | 0             | true                | 0      |
| 2003           | kippnewark | 2             | true                | 1      |
| 2004           | kippnewark | 2             | false               | 0      |
| 2005           | kippnewark | 2             | no row              | 0      |
| 3001           | kippcamden | 0             | true                | null   |

No row for 9999 appears in the output.

`test_pid_504_tf_writes_back_when_no_active_plans`, with an empty rollup:

| student_number | region     | enroll_status | S_NJ_STU_X `is_504` | expect |
| -------------- | ---------- | ------------- | ------------------- | ------ |
| 2001           | kippnewark | 0             | false               | 0      |
| 2002           | kippnewark | 0             | true                | 1      |
| 3001           | kippcamden | 0             | true                | null   |

- [ ] **Step 3: Run them to see them fail**

Run:
`uv run dbt test --select rpt_powerschool__autocomm_students,test_type:unit --target dev --defer --favor-state --state <wt>/src/dbt/kipptaf/target/prod --project-dir <wt>/src/dbt/kipptaf`
Expected: FAIL, because the column does not exist yet.

- [ ] **Step 4: Implement the column**

Left join the rollup and `stg_powerschool__s_nj_stu_x`. Both joins use
`_dbt_source_project` (A10); `njs` joins on
`se.students_dcid = njs.studentsdcid`. Derive a per-region flag for "the rollup
has any row", and compute the case in _Global Constraints_ as
`s_nj_stu_x__pid_504_tf`. Keep function nesting to 1 level (S8) by naming the
intermediate values in a CTE. Every other column and filter stays as it is.

- [ ] **Step 5: Complete the properties file**

Add:

- A model description.
- A model-level `dbt_utils.unique_combination_of_columns` on
  `[student_number, code_location]` at `severity: error`.
- A description on every column.
- The new column with `data_type: int64`, a description of the write-back rule,
  and `contains_pii: true`.
- PII tags on the existing tier 1–3 columns: `student_number`, `student_web_id`,
  `student_web_password`, `web_id`, `web_password`, and
  `u_studentsuserfields__studentemail`. Also tag the lunch, retention,
  graduation-pathway, and FAFSA columns.

- [ ] **Step 6: Build and test**

Run:
`uv run dbt build --select int_edplan__section_504_active_plan_rollup rpt_powerschool__autocomm_students --target dev --defer --favor-state --state <wt>/src/dbt/kipptaf/target/prod --project-dir <wt>/src/dbt/kipptaf 2>&1 | tail -n 15`
Expected: both unit tests, the grain test, and the contract pass.

- [ ] **Step 7: Check against prod**

BigQuery MCP: compare the dev view with prod
`kipptaf_extracts.rpt_powerschool__autocomm_students`, measured the same minute.
Expected:

- The Newark row counts are equal.
- The Newark 1s equal the active plans among currently enrolled students.
- Every non-Newark row has a null in the new column.
- No withdrawn Newark row differs from `if(is_504, 1, 0)` in prod
  `stg_powerschool__s_nj_stu_x`.

- [ ] **Step 8: Lint and commit**

Run trunk check as in Task 1. Commit
`feat(dbt): add PID_504_TF to the student AutoComm model` with `Refs #6423`.

### Task 3: Newark wrapper

**Files:**

- Modify:
  `src/dbt/kippnewark/models/extracts/powerschool/rpt_powerschool__autocomm_students.sql`
- Modify:
  `src/dbt/kippnewark/models/extracts/powerschool/properties/rpt_powerschool__autocomm_students.yml`

**Interfaces:**

- Consumes: Task 2's column, through `source("kipptaf_extracts", ...)`.
- Produces: the 21-column Newark file, with `s_nj_stu_x__pid_504_tf` last.

- [ ] **Step 1: Add the column**

Append `s_nj_stu_x__pid_504_tf` as the last select item. In the properties file,
add the column with `data_type: int64` only; the wrapper is contract-only.

- [ ] **Step 2: Build in dev**

Run:
`uv run dbt build --select rpt_powerschool__autocomm_students --target dev --project-dir <wt>/src/dbt/kippnewark 2>&1 | tail -n 10`
Expected: PASS. The compiled SQL reads `zz_<user>_kipptaf_extracts` (check
`target/compiled`).

- [ ] **Step 3: Check positions and values**

BigQuery MCP:

- `INFORMATION_SCHEMA.COLUMNS` on the dev wrapper lists 21 columns, with
  `s_nj_stu_x__pid_504_tf` at `ordinal_position` 21.
- The first 20 columns of the dev wrapper `except distinct` the prod wrapper, in
  both directions, return 0 rows.
- `git -C <wt> diff --stat origin/main -- src/dbt/kippcamden src/dbt/kipppaterson`
  is empty.

- [ ] **Step 4: Commit**

Commit `feat(dbt): send PID_504_TF in Newark's student AutoComm` with
`Refs #6423`.

### Task 4: Staging copy, PR, and CI

- [ ] **Step 1: Ask for the staging write**

Ask the user to approve seeding
`zz_stg_kippnewark_edplan.stg_edplan__section_504_student_report` from prod.
After a yes in the turn right before it, run it alone:

```bash
uv run dbt clone --select stg_edplan__section_504_student_report --target staging --state <wt>/src/dbt/kippnewark/target/prod --full-refresh --project-dir <wt>/src/dbt/kippnewark
```

Expected: `PASS=1`, and the `zz_stg` row count equals prod.

- [ ] **Step 2: Push and open the PR**

Lint every changed file, push, and open the PR from the template with
`Closes #6423`. Reviewer Notes cover:

- The 21-column change.
- The write-back rule.
- The first-night counts as aggregates.
- That CI builds only the kipptaf side, so the Newark wrapper was checked
  locally.

- [ ] **Step 3: Check CI**

dbt Cloud CI passes. On the CI schema, re-run Task 2 Step 7's Newark counts.

### Task 5: Rollout after merge

- [ ] **Step 1: Confirm the deploy**

Dagster reloaded kipptaf and kippnewark on the merge commit. The kipptaf
pass-through, rollup, and AutoComm view rebuilt before the Newark wrapper. Prod
`kippnewark_extracts.rpt_powerschool__autocomm_students` has 21 columns. All of
this must hold before the next 03:05 run.

- [ ] **Step 2: Confirm the PowerSchool target**

Ask the user to confirm that Newark's student AutoComm import maps
`S_NJ_STU_X.PID_504_TF` as its 21st target for the next 03:30 import.

- [ ] **Step 3: Send the turn-off list**

Build the list of currently enrolled Newark students flagged in PowerSchool with
no active plan, from prod. Put it in a restricted Google Sheet in the user's
Drive (`google-workspace` skill). Confirm Felicia Harris's and Kara Brockett's
addresses with the user, and share only with them, after the user says yes.

- [ ] **Step 4: Check the first import**

Check two things:

- The next morning, the 03:05 PowerSchool extract run succeeded.
- After the next PowerSchool pull, current Newark students' `is_504` in prod
  `stg_powerschool__s_nj_stu_x` equals the active-plan list, apart from that
  day's changes. Withdrawn students' values are unchanged from the day before.

Post the region counts on #6423, with no cell under 10.
