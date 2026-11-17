# Newark 504 Status Dimension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Newark's AutoComm 504 column reads EdPlan plans from a new
enrollment-bound mart, `dim_student_504_status`, instead of two intermediates.

**Architecture:** A students-folder intermediate turns EdPlan 504 events into
plan windows. The dim matches those windows to enrollment stints, as
`dim_student_iep_status` does. The kipptaf AutoComm view joins the dim on
`student_enrollment_key` and compares the window to today. Withdrawn students
write back the roster's existing `is_504`.

**Tech Stack:** dbt (BigQuery), kipptaf project. No Dagster or Newark wrapper
change.

**Spec:** `docs/superpowers/specs/2026-11-16-newark-autocomm-504-design.md`,
section _Revision 2026-11-17: 504 status dimension_. Read it first; it overrides
the original plan `docs/superpowers/plans/2026-11-16-newark-autocomm-504.md`
wherever they differ.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-newark-autocomm-504`
  (`<wt>`). `git -C <wt>`, absolute paths, `uv run` always. Branch
  `anthonygwalters/feat/claude-newark-autocomm-504` (PR #6424).
- kipptaf paths below are relative to `<wt>/src/dbt/kipptaf/`.
- Dev build command (call it `BUILD <selector>`), run from `<wt>`:
  `uv run dbt build --select <selector> --project-dir src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`
- Plans only: `event_selector` in `'Currently Valid: Section 504 Plan'`,
  `'Previous: Section 504 Plan'`. Eligibility rows never enter.
- No `current_date` in the intermediate or the dim. Only the `rpt_` compares to
  `current_date('{{ var("local_timezone") }}')`.
- Active in the extract: `is_current_plan`, and
  `effective_date_start_key <= today <= effective_date_end_key`, on the roster
  row's own stint (`student_enrollment_key`).
- Keys through macros (A7): `{{ student_key(...) }}`,
  `{{ student_enrollment_key(student_number, _dbt_source_project, academic_year, entrydate) }}`.
- PII: tag student-level columns `contains_pii: true`; fixtures use made-up
  student numbers (1001-style). No real values in commits or GitHub.
- No dedup (`distinct`, `qualify`, `dbt_utils.deduplicate`) anywhere. A grain
  failure means stop and report.
- SQL rules S1-S20 (`.claude/rules/dbt-sql.md`), notably S8 (one level of
  nesting) and S10 (derived conditions become named columns upstream).

## Review Focus

- A previous and a current plan on the same `begin_date`: the previous one must
  drop, or the intermediate's grain test fails. Pinned in Task 1.
- A current plan followed by a later previous plan (one real student): the
  current plan keeps its own end date. Pinned in Task 1.
- A plan spanning the summer: 2 dim rows, one per stint, each cut to its stint.
  Pinned in Task 2.
- A previous plan whose end date has not passed, with no later plan: must yield
  0 in the extract, because only current plans count. Pinned in Task 3.
- A current plan that starts after today, inside the current stint: 0 until it
  starts. Pinned in Task 3.

---

### Task 1: `int_students__section_504_plans`

**Files:**

- Create: `models/students/intermediate/int_students__section_504_plans.sql`
- Create:
  `models/students/intermediate/properties/int_students__section_504_plans.yml`

**Interfaces:**

- Consumes: `ref("stg_edplan__section_504_student_report")` (kipptaf union;
  columns `student_number` int64, `_dbt_source_project`, `event_selector`,
  `begin_date` date, `end_date` date).
- Produces: one row per `student_number`, `_dbt_source_project`,
  `plan_start_date`, with `student_number` int64, `_dbt_source_project` string,
  `plan_start_date` date, `plan_end_date` date, `is_current_plan` bool.

- [ ] **Step 1: Write the unit test** `test_section_504_plan_windows` in the
      properties file, input `ref('stg_edplan__section_504_student_report')`,
      `format: sql`, all rows `_dbt_source_project = 'kippnewark'`:

| student | event_selector                                         | begin      | end        |
| ------- | ------------------------------------------------------ | ---------- | ---------- |
| 1001    | Previous: Section 504 Plan                             | 2024-09-01 | 2025-12-31 |
| 1001    | Currently Valid: Section 504 Plan                      | 2025-09-15 | 2026-09-14 |
| 1002    | Previous: Section 504 Plan                             | 2025-10-01 | 2026-10-01 |
| 1002    | Currently Valid: Section 504 Plan                      | 2025-10-01 | 2026-09-30 |
| 1003    | Currently Valid: Section 504 Plan                      | 2025-01-10 | 2026-01-09 |
| 1003    | Previous: Section 504 Plan                             | 2025-06-01 | 2026-06-01 |
| 1004    | Currently Valid: Section 504 Eligibility Determination | 2025-01-01 | 2026-01-01 |
| null    | Currently Valid: Section 504 Plan                      | 2025-01-01 | 2026-01-01 |
| 1005    | Currently Valid: Section 504 Plan                      | 2025-02-01 | null       |

Expected rows (student, start, end, is_current_plan):

| student | plan_start_date | plan_end_date | is_current_plan |
| ------- | --------------- | ------------- | --------------- |
| 1001    | 2024-09-01      | 2025-09-14    | false           |
| 1001    | 2025-09-15      | 2026-09-14    | true            |
| 1002    | 2025-10-01      | 2026-09-30    | true            |
| 1003    | 2025-01-10      | 2026-01-09    | true            |
| 1003    | 2025-06-01      | 2026-06-01    | false           |
| 1005    | 2025-02-01      | 9999-12-31    | true            |

Also: `dbt_utils.unique_combination_of_columns` on `student_number`,
`_dbt_source_project`, `plan_start_date` at `error`; `not_null` on
`plan_start_date` at `error`. Model description from the spec. Every column gets
a description; `student_number`, dates and `is_current_plan` get
`contains_pii: true`.

- [ ] **Step 2: Run it and see it fail** (model missing):
      `uv run dbt test --select "int_students__section_504_plans,test_type:unit" --project-dir src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
      Expected: error, model not found.

- [ ] **Step 3: Write the model.** Filter to the 2 selectors and non-null
      `student_number`. In a CTE, compute `is_current_plan` and
      `next_plan_start_date = lead(begin_date) over (partition by student_number, _dbt_source_project order by begin_date, is_current_plan)`
      (false sorts first, so a current plan is "next" on a shared date). In a
      second CTE,
      `day_before_next_plan = date_sub(next_plan_start_date, interval 1 day)`.
      `plan_end_date`: current → `coalesce(end_date, '9999-12-31')` (cast as
      date); previous → the earlier of `end_date` and `day_before_next_plan`, or
      `end_date` when there is no next plan. Final
      `where plan_end_date >= plan_start_date`.

- [ ] **Step 4: Run the unit test.** Same command. Expected: PASS.

- [ ] **Step 5: Seed your personal Newark source copy, then build.** kipptaf's
      dev `source()` reads `zz_<you>_kippnewark_edplan`, which `--favor-state`
      does not cover:
      `uv run dbt clone --select stg_edplan__section_504_student_report --project-dir src/dbt/kippnewark --target dev --state /workspaces/teamster/src/dbt/kippnewark/target/prod`
      Then
      `BUILD stg_edplan__section_504_student_report int_students__section_504_plans`.
      Expected: both pass, including the grain and not_null tests.

- [ ] **Step 6: Check against prod.** Via BigQuery MCP on your dev relation:
      rows with `is_current_plan` equal 142 (current plans on 2026-11-17, or
      today's count from
      `kippnewark_edplan.stg_edplan__section_504_student_report`); none has
      `plan_end_date < plan_start_date`.

- [ ] **Step 7: Commit** `feat(dbt): add int_students__section_504_plans` (stage
      the 2 files by name).

### Task 2: `dim_student_504_status`

**Files:**

- Create: `models/marts/dimensions/dim_student_504_status.sql`
- Create: `models/marts/dimensions/properties/dim_student_504_status.yml`
- Modify: `models/exposures/cube.yml` (add `ref("dim_student_504_status")` to
  `cube_semantic_layer.depends_on`, alphabetical, before
  `dim_student_bucket_status` or wherever the order puts it)

**Interfaces:**

- Consumes: Task 1's model; `ref("int_students__student_enrollment_union")`
  (`student_number`, `_dbt_source_project`, `academic_year`, `entrydate`,
  `exitdate`).
- Produces columns, in this order: `student_504_status_key` string (PK),
  `_dbt_source_project` string, `effective_date_start_key` date,
  `effective_date_end_key` date, `is_current_plan` bool, `student_key` string,
  `student_enrollment_key` string.

- [ ] **Step 1: Write the unit test** `test_504_status_stint_windows`. Inputs:
      Task 1's model and the enrollment union, `format: sql`.
  - Student 2001 has 1 current plan 2026-03-01 to 2027-03-01, and stints (2025,
    entry 2025-09-01, exit 2026-06-30) and (2026, entry 2026-09-01, exit
    2027-06-30). Expect 2 rows: 2026-03-01 to 2026-06-29, and 2026-09-01 to
    2027-03-01.
  - Student 2002 has a plan 2027-09-01 to 2028-09-01 and the same 2026 stint
    only. Expect no row.
  - Student 2003 has a plan 2026-10-01 to 2027-10-01 and a 2026 stint entered
    2026-09-01 with a null `exitdate`. Expect 1 row, 2026-10-01 to 2027-10-01.
  - A graduate placeholder row (null `entrydate`) for 2001 adds nothing.
  - Expect `student_enrollment_key` for 2001's 2026 row as
    `to_hex(md5(concat('2001', '-', 'kippnewark', '-', '2026', '-', '2026-09-01')))`
    (the fixture precedent is
    `int_branchingminds__intervention_plans_rollup.yml`). Other key columns may
    be left out of `expect`.

- [ ] **Step 2: Run it and see it fail** (model missing), with the Task 1 test
      command and this model's name.

- [ ] **Step 3: Write the model.** Copy `dim_student_iep_status`'s `enrollments`
      CTE (half-open `enrollment_end`, drop null `entrydate`) and its `nj_leg`
      overlap join (inner join, region-keyed, start = later of the 2 starts, end
      = earlier of the 2 ends). No island CTEs, no Miami branch.
      `student_504_status_key` =
      `dbt_utils.generate_surrogate_key(["student_number", "_dbt_source_project", "effective_date_start"])`.
      `student_key` and `student_enrollment_key` through their macros.

- [ ] **Step 4: Write the properties.** Mirror `dim_student_iep_status.yml`:
      Dagster `asset_key: [kipptaf, marts, dim_student_504_status]`, group
      `marts`; PK constraint `warn_unsupported: false` plus `unique`; `not_null`
      on `_dbt_source_project`, both date keys and `is_current_plan`;
      `config.meta.foreign_key` on the 2 date keys (`dim_dates.date_key`),
      `student_key` (`dim_students`) and `student_enrollment_key`
      (`dim_student_enrollments`). Descriptions say what a value means, not
      where it comes from (`marts/CLAUDE.md`). No `is_current` column. PII tags
      on the student-level columns.

- [ ] **Step 5: Run the unit test.** Expected: PASS.

- [ ] **Step 6: Build.**
      `BUILD int_students__section_504_plans dim_student_504_status` (select
      Task 1's model too, so `--favor-state` does not point it at prod, where it
      does not exist). Expected: pass, PK `unique` included.

- [ ] **Step 7: Check against prod data** via BigQuery MCP on the dev dim:
      Newark rows with `is_current_plan` whose window includes today, joined to
      prod `kipptaf_extracts.int_extracts__student_enrollments` (2026,
      `rn_year = 1`, `grade_level != 99`, `enroll_status = 0`) on the recomputed
      `student_enrollment_key`, number 135. That is the first build's enrolled
      count on 2026-11-16; if today's differs, it must equal today's count of
      enrolled students with a Currently Valid plan ending today or later.

- [ ] **Step 8: Commit** `feat(dbt): add dim_student_504_status` (3 files by
      name).

### Task 3: AutoComm reads the dim; remove the old intermediates

**Files:**

- Modify: `models/extracts/powerschool/rpt_powerschool__autocomm_students.sql`
- Modify:
  `models/extracts/powerschool/properties/rpt_powerschool__autocomm_students.yml`
- Delete:
  `models/edplan/intermediate/int_edplan__section_504_active_plan_rollup.sql`
  and
  `models/edplan/intermediate/properties/int_edplan__section_504_active_plan_rollup.yml`
- Delete: `models/students/intermediate/int_students__section_504_status.sql`
  and
  `models/students/intermediate/properties/int_students__section_504_status.yml`
  (both never shipped, so a delete, not a disable)

**Interfaces:**

- Consumes: Task 2's `student_enrollment_key`, `is_current_plan`,
  `effective_date_start_key`, `effective_date_end_key`, `_dbt_source_project`;
  the roster's `is_504`.
- Produces: `s_nj_stu_x__pid_504_tf` unchanged in name, type (int64) and
  position (last).

- [ ] **Step 1: Rewrite the unit tests** in the `rpt_` properties. Replace the
      `int_students__section_504_status` input with
      `ref('dim_student_504_status')`, `format: sql`, columns
      `student_enrollment_key`, `_dbt_source_project`, `is_current_plan`,
      `effective_date_start_key`, `effective_date_end_key`. Give each roster
      fixture row `entrydate: 2026-09-01` and an `is_504`, and build each dim
      key with the `to_hex(md5(concat(...)))` form from Task 2. Keep every
      existing case and expected value. Add, in
      `test_pid_504_tf_mirrors_edplan`:
  - an enrolled student whose only dim row is a previous plan covering today →
    0;
  - an enrolled student whose current plan starts after today → 0. Use dates
    relative to `current_date('America/New_York')` in the fixture so the test
    does not age.
  - Withdrawn and no-active-plans rows read `is_504` from the roster fixture.

- [ ] **Step 2: Run them and see them fail**
      (`uv run dbt test --select "rpt_powerschool__autocomm_students,test_type:unit" ...`):
      the model still reads the old intermediates.

- [ ] **Step 3: Change the SQL.**
  - A CTE over the roster that adds `student_enrollment_key` through the macro
    and applies the existing `where` (S10: no macro in `on`). The final select
    reads it as `se`.
  - `active_504_plans`: dim rows with `is_current_plan`,
    `effective_date_start_key <= current_date(...)` and
    `effective_date_end_key >= current_date(...)`.
  - `edplan_504_regions`: `count(*) as n_active_504_plans` from
    `active_504_plans` grouped by `_dbt_source_project`.
  - Left join `active_504_plans` on `student_enrollment_key`; drop the
    `int_students__section_504_status` join.
  - In the `case`: `if(se.is_504, 1, 0)` replaces both
    `if(s504.is_504_state_field, 1, 0)`; the plan branch tests that the join
    matched. Branch order and the `'kippnewark'` guard with its comment stay.

- [ ] **Step 4: Update the `s_nj_stu_x__pid_504_tf` description** for the new
      rule: active means today falls in a current plan's window on the student's
      stint; withdrawn rows return PowerSchool's value, which can be the value
      copied at withdrawal (the spec's accepted risk). Keep the partial-file
      sentence.

- [ ] **Step 5: Delete the 4 files** listed above, then
      `rg -n 'section_504_status|section_504_active_plan_rollup' src/dbt docs --glob '*.{sql,yml,md}'`
      from `<wt>`. Expected: hits only in the 2026-11-16 spec and plan
      (history), none in `src/dbt`.

- [ ] **Step 6: Run the unit tests.** Expected: PASS.

- [ ] **Step 7: Build.**
      `BUILD stg_edplan__section_504_student_report int_students__section_504_plans dim_student_504_status rpt_powerschool__autocomm_students`.
      Expected: pass, including the grain test at `error`.

- [ ] **Step 8: Compare to the first build** via BigQuery MCP. On the dev
      `rpt_`, Newark rows: count equals prod's roster count today; no null in
      the column; non-Newark rows are null. 1s equal Step 7 of Task 2's count.
      Every withdrawn row equals `if(is_504, 1, 0)` from prod
      `kipptaf_extracts.int_extracts__student_enrollments`. Report counts only.

- [ ] **Step 9: Commit**
      `refactor(dbt): read the 504 status dim in the Newark     AutoComm` (stage
      the 2 modified and 4 deleted files by name).

### Task 4: Branch checks and push

- [ ] **Step 1: Layer check**, from `<wt>`:
      `uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir src/dbt/kipptaf`,
      then
      `git -C <wt> diff -U0 --no-renames origin/main...HEAD > <scratchpad>/pr.diff`,
      then
      `uv run python scripts/check_dbt_standard.py --project-dir src/dbt/kipptaf --diff <scratchpad>/pr.diff`.
      Expected: no new violation and no A4 warning for the new models.

- [ ] **Step 2: Lint** the changed SQL, YAML and the plan:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
      from `<wt>`. Fix findings; formatting is the commit hook's.

- [ ] **Step 3: Push**
      `git -C <wt> push origin anthonygwalters/feat/claude-newark-autocomm-504`.

- [ ] **Step 4: Update the PR body** (`gh api -X PATCH ... -F body=@<file>`,
      from a raw GET): the 4-part summary becomes the dim design; `Refs #6425`
      becomes `Closes #6425`; Reviewer Notes name the start-date rule change for
      special education; the A2 and A4 notes go.
