# Prior-Year State Scores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give prior-year state scores 1 home, as a `benchmark_academic_year`
column on `int_assessments__state_scores`, and move its 3 consumers onto it with
no value changes.

**Architecture:** The new column records the school year a state score serves as
a prior-year benchmark. Its value depends only on the test window. Each consumer
keeps its own rule for which tests and subjects count. It drops its own year
math and joins or filters on the column instead.
`int_assessments__fast_previous_year` stops reading `stg_fldoe__fast` and
`base_powerschool__student_enrollments`.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** the design decision comment on #5911
(https://github.com/TEAMSchools/teamster/issues/5911#issuecomment-6420614818).

## Global Constraints

- The refactor preserves values. Every consumer column keeps its value and its
  data type. Any difference is a defect, unless it is listed and explained in
  the PR.
- `benchmark_academic_year` rule:
  - `academic_year + 1` for NJ `administration_period = 'Spring'`, FL
    `administration_period = 'PM3'`, and every FL `assessment_name = 'EOC'` row
    in any window.
  - `academic_year` for FL `assessment_name = 'FAST'` with
    `administration_period = 'PM1'`.
  - null otherwise (NJGPA Fall, FAST PM2).
- The grade 8 NJSLA Algebra filter stays in `int_assessments__goal_benchmarks`
  only. Do not add it to the roster, and do not remove it. An Asana approval
  task tracks the decision.
- The roster keeps its state student id join key. The existing
  `/* TODO: find records that only match on SID */` stays.
- `int_assessments__state_scores` has 10 consumers. Add the column. Do not
  rename or retype any existing column.
- Run dbt through `uv run`. Run local builds per the `dbt-local-dev` skill:
  invoke it before the first build.

## Review Focus

- FL EOC in a non-PM3 window gets `academic_year + 1`, not null. Prod has only
  PM3 EOC today, so only the unit test covers this case (Task 1).
- `scale_score` is `NUMERIC` in `int_assessments__state_scores` and `INT64` in
  `stg_fldoe__fast`. `int_assessments__fast_previous_year` must cast it back, or
  `prev_pm3_scale` and both `scale_points_*` columns change type in the payout
  roster (Task 4).
- Percentile ranks move if any rank partition gains or loses a row. Compare
  ranks row by row, not just counts (Task 5).
- The roster's left join must not fan out once it reads the long table directly.
  Its `on` filters must narrow to NJSLA plus FAST PM3 with a non-null scale
  score, as the CTE did (Task 3).
- The 8 FAST PM3 rows with no `student_number` must stay out of
  `int_assessments__fast_previous_year`. Joining on `fleid` to
  `state_student_id` keeps them out today (Task 4).

---

### Task 1: `benchmark_academic_year` on `int_assessments__state_scores`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_scores.sql`
  (final select)
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__state_scores.yml`
  (column entry and `unit_tests:`)

**Interfaces:**

- Produces: `benchmark_academic_year` (`int64`, nullable) on
  `int_assessments__state_scores`.

- [ ] **Step 1: Write the failing unit test**
      `int_assessments__state_scores__benchmark_academic_year` in the properties
      yml. Mock `int_assessments__state_nj_scores`,
      `int_fldoe__all_assessments`, and
      `stg_google_sheets__assessments__vendor_subject_crosswalk` (no rows), with
      fake ids only. Use 6 input rows, all with `academic_year` 2024, and expect
      these `benchmark_academic_year` values:

  | score_source | assessment_name | administration_period | expected |
  | ------------ | --------------- | --------------------- | -------- |
  | state_nj     | NJSLA           | Spring                | 2025     |
  | state_nj     | NJGPA           | Fall                  | null     |
  | state_fl     | FAST            | PM1                   | 2024     |
  | state_fl     | FAST            | PM2                   | null     |
  | state_fl     | FAST            | PM3                   | 2025     |
  | state_fl     | EOC             | PM2                   | 2025     |

  The FL mock sets `administration_window` (the state_scores FL branch renames
  it to `administration_period`). The NJ mock sets `administration_period`.

- [ ] **Step 2: Run it to verify that it fails**

  Run:
  `uv run dbt test --select int_assessments__state_scores,test_type:unit --project-dir src/dbt/kipptaf`
  Expected: FAIL, because `benchmark_academic_year` is not a column.

- [ ] **Step 3: Add the column.** Add a `case` as the last item of the final
      select (S6: after the `coalesce`). Add the yml column entry. Its
      description states the rule from _Global Constraints_ and says that
      consumers choose which tests and subjects count.

- [ ] **Step 4: Run the unit test again.** The same command must PASS.

- [ ] **Step 5: Commit**
      `refactor(dbt): add benchmark_academic_year to int_assessments__state_scores`

### Task 2: `int_assessments__goal_benchmarks` reads the column

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__goal_benchmarks.sql:27-30`

**Interfaces:**

- Consumes: `benchmark_academic_year` (Task 1).

- [ ] **Step 1: Swap the year expression.** In the first `benchmark_union`
      branch, replace `academic_year + if(...) as academic_year` and its comment
      with `benchmark_academic_year as academic_year`. Leave the `where` clause,
      the Star and i-Ready branches, and the grade 8 Algebra filter unchanged.
      Move the column to its S6 position: plain columns before functions.

- [ ] **Step 2: Build it.** Run
      `uv run dbt build --select int_assessments__state_scores int_assessments__goal_benchmarks`
      per `dbt-local-dev`. Expected: PASS, including the uniqueness test.

- [ ] **Step 3: Commit**
      `refactor(dbt): read benchmark_academic_year in int_assessments__goal_benchmarks`

### Task 3: Roster drops `prev_yr_state_test`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects.sql:52-72,220,243,290-296`

**Interfaces:**

- Consumes: `benchmark_academic_year` (Task 1).

- [ ] **Step 1: Replace the CTE with a direct join.** Delete the
      `prev_yr_state_test` CTE. Left join
      `{{ ref("int_assessments__state_scores") }} as py` on:
  - `co.state_studentnumber = py.state_student_id`
  - `co.academic_year = py.benchmark_academic_year`
  - `co._dbt_source_project = py._dbt_source_project`
  - `sj.illuminate_subject_area = py.illuminate_subject_area`

  Move the CTE's test filter into the `on` clause as is: the NJSLA branch, or
  the FAST PM3 branch with a non-null scale score. Also move the CTE's
  NJSLA/NJGPA comment. Rename the 2 select references from
  `py.state_test_aggregated_proficiency` to `py.aggregated_proficiency`. Keep
  the existing SID `TODO`.

- [ ] **Step 2: Build it.** Run
      `uv run dbt build --select int_extracts__student_enrollments_subjects`.
      Expected: PASS, including its uniqueness test.

- [ ] **Step 3: Commit**
      `refactor(dbt): join prior-year state scores directly in student enrollments subjects`

### Task 4: Rebuild `int_assessments__fast_previous_year` on shared models

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__fast_previous_year.sql:12-63`
  (`prev_year` CTE only)

**Interfaces:**

- Consumes: `benchmark_academic_year` (Task 1),
  `int_extracts__student_enrollments`.
- Produces: the same output columns, names, and types as today. Downstream
  consumers: `rpt_gsheets__kippmiami_payout_roster`, `rpt_tableau__miami_fast`,
  and `int_extracts__student_enrollments_subjects`.

- [ ] **Step 1: Swap the sources in `prev_year`.**
  - Replace `base_powerschool__student_enrollments` with
    `int_extracts__student_enrollments`. The filter stays
    `rn_year = 1 and region = 'Miami' and grade_level != 99`.
  - Replace `stg_fldoe__fast` with `int_assessments__state_scores`. Join on
    `co.fleid = pp.state_student_id` and
    `co.academic_year = pp.benchmark_academic_year`, with
    `pp.score_source = 'state_fl'`, `pp.assessment_name = 'FAST'`, and
    `pp.administration_period = 'PM3'`.
  - Map the columns: `student_id` → `state_student_id`, `assessment_grade` →
    `test_grade`, `assessment_subject` → `raw_subject`, `achievement_level` →
    `performance_level_label`, `achievement_level_int` → `performance_level`.
  - Emit `cast(scale_score as int64) as prev_pm3_scale` (S9). Rank on that
    column. The rank partitions use `academic_year`. Keep that partition value,
    which is the test year, as `pp.academic_year`.

- [ ] **Step 2: Build it.** Run
      `uv run dbt build --select int_assessments__fast_previous_year+`.
      Expected: PASS, including the
      `student_number, academic_year, assessment_subject` uniqueness test.

- [ ] **Step 3: Confirm the source swap.** `rg` the file for `stg_fldoe__fast`
      and `base_powerschool__student_enrollments`. Expected: no matches.

- [ ] **Step 4: Commit**
      `refactor(dbt): build int_assessments__fast_previous_year on shared state scores`

### Task 5: Parity proof and PR

- [ ] **Step 1: Compare each model, dev against prod,** with BigQuery MCP
      `execute_sql_readonly`. For each model, run `except distinct` both ways
      over every column. Expected: 0 rows each way, with equal row counts.
  - `int_assessments__fast_previous_year`: every column, which covers the ranks
    row by row.
  - `int_assessments__goal_benchmarks`
  - `int_extracts__student_enrollments_subjects`
  - `rpt_gsheets__kippmiami_payout_roster`: every column fed by
    `int_assessments__fast_previous_year`.
  - `rpt_tableau__miami_fast`: the same.

- [ ] **Step 2: Compare column types.** Diff `INFORMATION_SCHEMA.COLUMNS`, dev
      against prod, for `int_assessments__fast_previous_year`. Expected:
      identical `data_type` on every column.

- [ ] **Step 3: Handle any difference.** If any value differs, list it in the
      PR. A payout roster difference also goes on Kevin Verhoff's Asana approval
      task. Do not ship a payout change without that sign-off.

- [ ] **Step 4: Lint.** From the worktree, run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed .sql/.yml/.md> </dev/null`.
      Fix any findings.

- [ ] **Step 5: Push and open the PR** from `.github/pull_request_template.md`.
      Write `Closes #5911` in the body, because the branch is linked. Report the
      parity results and note that #5893 already added `_dbt_source_project` to
      the `fp` and `pr` joins.
