# DIBELS Benchmark expected tests (PR PM1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested intermediate with 1 row per student, Benchmark administration
and expected measure, matching the dashboard model's Benchmark branch; 2
Benchmark goal dimensions; and the Benchmark fact built in dev for PR PM4.

**Architecture:** `int_assessments__dibels_benchmark_expected_tests` ports the
BM branch of `rpt_tableau__dibels_dashboard` into a table, reading enrollment
from the same spine. A singular drift test compares it with the dashboard model.
The goal sheet feeds 1 intermediate and 2 dimensions. The fact is a thin select
over the intermediate, on its own branch, because it cannot merge until the A12
decision is made.

**Tech Stack:** dbt on BigQuery (`uv run dbt`), the BigQuery MCP for checks,
trunk for lint.

**Spec:**
`docs/superpowers/specs/2026-11-23-dibels-expected-test-facts-design.md`,
including its _Revision 2026-11-23_ section, which overrides the sections above
it. Read `.claude/skills/dibels-dashboard/references/model-architecture.md`
before Task 2.

## Global Constraints

- Do not edit `rpt_tableau__dibels_dashboard.sql`,
  `int_students__dibels_participation_roster.sql`, either criteria model, or any
  extract model.
- Branch A (mergeable):
  `anthonygwalters/feat/claude-dibels-benchmark-expected-tests`, from
  `origin/main`. Branch B (dev only):
  `anthonygwalters/feat/claude-dibels-benchmark-fact`, from branch A. Ask the
  user "worktree or branch switch" before creating either. Neither is linked to
  an issue.
- Every dbt call:
  `uv run dbt ... --project-dir <wt>/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Run `uv run dbt deps --project-dir <wt>/src/dbt/kipptaf` once per new
  worktree, in its own call.
- The fact does not go in branch A's PR. A12 fails it until the decision issue
  is settled.
- Students in scope are the dashboard's: `enroll_status in (0, 2, 3)`,
  `is_self_contained is not true`, `not is_out_of_district`, spine rows with
  `iready_subject = 'Reading'`.
- Every student-level column is tagged `config.meta.contains_pii: true`.
- Queries return aggregates only. Nothing in a commit, the PR or an issue names
  a student or shows a row. Counts under 10 read `<10` there.
- PRs carry `Refs #6473` and `Refs #6461`.
- Before any push of a branch that changes a `dibels` or `amplify` file under
  `src/dbt/`: ask the user, in these words, "We need to update the skill and ref
  doc — do you authorize the update checks?"

## Review Focus

1. A student who sat a Benchmark measure at 2 grades: 1 row, carrying the
   sitting at the enrolled grade. Pinned by Task 2 Step 5 (uniqueness) and a
   count in Task 3 Step 3.
2. A student who sat only at another grade: the row still carries that score and
   reads Tested, as on the dashboard. Pinned by Task 3 Step 3 (0 value
   differences on single-sitting keys).
3. A student expected to test who did not: the row exists with `expected_*`
   filled and score columns null. Pinned by Task 2 Step 6 (row count equals the
   dashboard's distinct keys).
4. A school and grade with no BM Goals paste yet: the fact's goal keys are null,
   not a placeholder hash. Pinned by Task 5 Step 3.
5. A region whose counts differ between 2 school rows on the goal sheet: the
   region goals dimension must not hold 2 rows for 1 key. Pinned by Task 1 Steps
   1 and 5.

---

### Task 1: Benchmark goals intermediate and 2 dimensions

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__dibels_benchmark_goals.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__dibels_benchmark_goals.yml`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_dibels_benchmark_school_goals.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_dibels_benchmark_region_goals.sql`
- Create: both dimensions' yml under `models/marts/dimensions/properties/`
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml` (add both dimensions to
  `cube_semantic_layer.depends_on`)

**Interfaces:**

- Consumes: `stg_google_sheets__dibels_bm_goals` (grain `academic_year`,
  `region`, `school`, `assessment_grade_int`, `period`).
- Produces:
  - `int_assessments__dibels_benchmark_goals`: same grain and columns as the
    staging model, All-students columns only (no `_iep`, no `_mll`).
  - `dim_dibels_benchmark_school_goals`: key `dibels_benchmark_school_goal_key`,
    hashed as
    `generate_surrogate_key(academic_year, region, school, assessment_grade_int, period)`;
    columns `academic_year`, `region`, `school`, `grade_level`
    (`assessment_grade_int`), `administration_period` (`period`), `n_students`,
    `n_students_at_above`, `n_students_below_well_below`,
    `n_students_at_above_expected`, `n_students_at_above_gap` (the 5
    `n_admin_season_school_gl_*` columns, in that order).
  - `dim_dibels_benchmark_region_goals`: key `dibels_benchmark_region_goal_key`,
    hashed as
    `generate_surrogate_key(academic_year, region, assessment_grade_int, period)`;
    columns `academic_year`, `region`, `grade_level`, `administration_period`,
    `goal_season` (`benchmark_goal_season`), `grade_goal`, `grade_range_goal`,
    and the same 5 count names from the `n_admin_season_region_gl_*` columns.

- [ ] **Step 1: Measure the sheet rows that would break the region grain**

```sql
with
    g as (
        select
            academic_year,
            region,
            assessment_grade_int,
            `period`,
            count(
                distinct format(
                    '%T',
                    (
                        benchmark_goal_season,
                        grade_goal,
                        grade_range_goal,
                        n_admin_season_region_gl_all,
                        n_admin_season_region_gl_at_above,
                        n_admin_season_region_gl_bl_wb,
                        n_admin_season_region_gl_at_above_expected,
                        n_admin_season_region_gl_at_above_gap
                    )
                )
            ) as n_combos,
        from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__dibels_bm_goals`
        group by academic_year, region, assessment_grade_int, `period`
    )

select academic_year, countif(n_combos > 1) as n_cells_varying,
from g
group by academic_year
```

Expected on 2026-11-23: 2 cells in academic year 2025, 0 in 2024 and 2026. Those
2 cells are hand-filled history where a region count differs between school
rows. Stop and ask the user which they want: correct the 2 cells on the BM Goals
sheet (the whole corrected tab, per the skill's sheet rule), or have the
dimension keep the larger value for those cells. Do not pick for them. Run
`uv run dbt build --select stg_google_sheets__dibels_bm_goals` after a sheet fix
and re-run this query.

- [ ] **Step 2: Write the intermediate and its yml**

A plain select of the All-students columns from the staging model.
`dbt_utils.unique_combination_of_columns` on the grain at `severity: error`.
Description on the model and every column.

- [ ] **Step 3: Write the school goals dimension**

Select from the intermediate, hash the key, rename as listed under _Interfaces_.
yml: `materialized: table`, the same `automation_condition.cron_schedule` as
`dim_assessment_goals` with a comment pointing to it, `primary_key` constraint
with `warn_unsupported: false` and `warn_unenforced: false`, `unique` on the key
at `severity: error`. No `foreign_key` constraints: it is a table mart.

- [ ] **Step 4: Write the region goals dimension**

`select distinct` over the region-grain columns of the intermediate, annotated
`-- grain projection, not dup-masking: region columns repeat on every school row`.
Same yml shape as Step 3. If the user chose the "larger value" rule in Step 1,
replace the `distinct` with a `group by` on the grain and `max()` on each value
column, and say so in the model description.

- [ ] **Step 5: Build and test**

```bash
uv run dbt build --select int_assessments__dibels_benchmark_goals dim_dibels_benchmark_school_goals dim_dibels_benchmark_region_goals <global flags> 2>&1 | tail -n 30
```

Expected: 3 models build, 3 uniqueness tests pass. The school dimension's row
count equals the staging model's. The region dimension's row count equals the
number of distinct (`academic_year`, `region`, `assessment_grade_int`, `period`)
in the staging model: check both with 1 count query.

- [ ] **Step 6: Lint and commit**

`trunk check --force --no-fix` on the 7 files, then
`git commit -m "feat(dbt): DIBELS benchmark goal dimensions"` with the `Refs`
footer.

### Task 2: The Benchmark expected-tests intermediate

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__dibels_benchmark_expected_tests.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__dibels_benchmark_expected_tests.yml`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments_subjects`,
  `int_google_sheets__dibels_expected_assessments`,
  `int_amplify__all_assessments`, `int_students__dibels_participation_roster`,
  `int_students__course_enrollments`.
- Produces: 1 row per `academic_year`, `student_number`, `expected_test`,
  `expected_round_number`, `expected_measure_standard`. Columns, in this order:
  - stint: `academic_year`, `student_number`, `_dbt_source_project`,
    `entrydate`, `region`, `schoolid`, `school`, `grade_level`;
  - expected: `expected_test`, `expected_round_number` (int64),
    `expected_measure_standard`, `expected_measure_name_code`,
    `expected_measure_name`, `expected_grade_level` (text),
    `expected_month_round`, `expected_start_date`, `expected_end_date`,
    `expected_round_selection`;
  - section: `ela_section_cc_dcid` (null when unscheduled), `is_scheduled`
    (bool);
  - score: `assessment_grade`, `client_date`, `measure_name`,
    `measure_name_code`, `measure_standard`, `measure_standard_score`,
    `measure_standard_level`, `measure_standard_level_int`,
    `measure_percentile`, `measure_semester_growth`, `measure_year_growth`,
    `boy_composite`, `moy_composite`, `eoy_composite`,
    `aggregated_measure_standard_level`, `foundation_measure_standard_level`;
  - roster: `expected_row_count`, `actual_row_count`, `completed_test_round`
    (bool), `participation_group`, `round_test_status`;
  - derived: `measure_test_status`.

- [ ] **Step 1: Record the target counts**

```sql
select
    academic_year,
    count(*) as n_rows,
    count(
        distinct format(
            '%T',
            (
                student_number,
                expected_test,
                expected_round_number,
                expected_measure_standard
            )
        )
    ) as n_keys,
from `teamster-332318.kipptaf_tableau.rpt_tableau__dibels_dashboard`
where model_type = 'BM'
group by academic_year
```

Record `n_keys` by year. On 2026-11-23, academic year 2026 had 139,370 rows and
139,348 keys.

- [ ] **Step 2: Port the BM branch**

Port `rpt_tableau__dibels_dashboard.sql` lines 4-44 (the BM half of
`stint_candidates`), 134-170 (`stint_anchors`, `picked_stints`) and 172-380 (the
BM select), with these changes and no others:

1. Read enrollment in 1 CTE, `enrollments`, that selects the stint columns from
   `int_extracts__student_enrollments_subjects` with the dashboard's 4 filters.
   Every later reference reads that CTE.
2. Drop every student, school and demographic column not listed under
   _Interfaces_. Drop the goal join and all `g.` columns. Drop every
   `cast(null as ...)` PM column.
3. Add `and b.model_type = 'BM'` to both joins to
   `int_amplify__all_assessments`.
4. Keep 1 score per key: rank the joined rows per grain key by
   `(b.assessment_grade_int = s.grade_level) desc, b.client_date desc` and keep
   rank 1. Apply the rank in a CTE of its own, after the joins.
5. From the ELA section join, keep `c.cc_dcid as ela_section_cc_dcid` and
   `c.students_student_number is not null as is_scheduled`.
6. `expected_round_number` stays int64. `completed_test_round` stays bool. Drop
   `completed_test_round_int`.

The rank in change 4 is a business-rule row pick, so the yml declares
`config.meta.standard_exempt: {A5: "Owner's rule for a student with 2 Benchmark sittings — the sitting at the enrolled grade wins"}`.

- [ ] **Step 3: Write the yml**

`materialized: table`, `automation_condition.cron_schedule: 0 4 * * *` with a
comment: it follows the spine's nightly rebuild and leads the Literacy
Dashboard's refresh; both schedules live in the spine's yml and
`models/exposures/tableau.yml`. Model-level
`dbt_utils.unique_combination_of_columns` on the 5 grain columns at
`severity: error`. Description and `contains_pii` on every student-level column.

- [ ] **Step 4: Check the cron is not after the dashboard refresh**

`rg -n -A14 'name: literacy_dashboard' src/dbt/kipptaf/models/exposures/tableau.yml | rg cron`

Expected: `0 5 * * *`. If it differs, set the intermediate's tick 1 hour earlier
than it and say so in the PR.

- [ ] **Step 5: Build**

```bash
uv run dbt build --select int_assessments__dibels_benchmark_expected_tests <global flags> 2>&1 | tail -n 20
```

Expected: the table builds and the uniqueness test passes.

- [ ] **Step 6: Reconcile the row count**

Count rows by `academic_year` in the dev table. Expected: equal to Step 1's
`n_keys` for every year (re-run Step 1 at the same time, since scores land
through the day). A difference means the port changed the row set: fix it before
Task 3.

- [ ] **Step 7: Lint and commit**

`git commit -m "feat(dbt): DIBELS benchmark expected-tests intermediate"`.

### Task 3: The drift test

**Files:**

- Create:
  `src/dbt/kipptaf/tests/int_assessments__dibels_benchmark_expected_tests__matches_dashboard.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: Task 2's table; `rpt_tableau__dibels_dashboard` where
  `model_type = 'BM'`.
- Produces: a test returning 1 row per violation, with columns `violation`
  (`dashboard_only`, `intermediate_only` or `value_differs`), `academic_year`,
  `expected_test`, `expected_measure_standard` and `n_keys`. It returns counts,
  never a student.

- [ ] **Step 1: Write the test**

1. Reference the dashboard model once. Project the grain key and the compared
   columns, as distinct rows. The dashboard holds 2 rows for a key where a
   student sat a measure at 2 grades; keep both.
2. Compared columns: every score, roster and derived column under Task 2's
   _Interfaces_, plus `expected_measure_name_code`, `expected_start_date`,
   `expected_end_date`, and `scheduled = 1` against `is_scheduled`. Not
   `expected_round_selection`.
3. A key the dashboard holds and the intermediate does not is `dashboard_only`.
   The reverse is `intermediate_only`. A key both hold is `value_differs` when
   none of the dashboard's rows for that key equals the intermediate's row on
   every compared column. Compare with a `to_json_string` of the compared
   columns, built in the same column order on both sides.
4. Final select: group to the 5 output columns.

Set no severity in the test's SQL: the project default is `warn`, which is what
this test starts at. In `tests/properties.yml` add the entry with a description
(what the test compares, that it retires when the dashboard model reads the
facts, and that a failure means one side's logic changed without the other) and
`meta.dagster.ref.name: int_assessments__dibels_benchmark_expected_tests`. Leave
a `# TODO(#6473): flip to error once this returns 0 rows in prod` comment above
the entry.

- [ ] **Step 2: Watch it fail on a deliberate break**

In the dev table's model, temporarily change `measure_test_status` to always
return `'Tested'`, rebuild, and run the test.

```bash
uv run dbt test --select int_assessments__dibels_benchmark_expected_tests__matches_dashboard <global flags> 2>&1 | tail -n 12
```

Expected: WARN with `value_differs` rows. Revert the change and rebuild.

- [ ] **Step 3: Run it for real**

Expected: 0 rows. Any row needs a named cause before the task is done. Then
count, in the dev table, the keys where `assessment_grade` differs from
`grade_level`, by year, and confirm no key appears twice: that is the 2-sitting
rule holding.

- [ ] **Step 4: Parse, lint and commit**

`uv run dbt parse --no-partial-parse` (singular-test descriptions bind only on a
full parse), trunk check, then
`git commit -m "test(dbt): DIBELS benchmark intermediate matches the dashboard model"`.

### Task 4: Reference doc, skill, checks, push and PR

**Files:**

- Modify: `docs/models/dibels-dashboard-data-model.md`
- Modify: `.claude/skills/dibels-dashboard/SKILL.md` (1 route row)
- Modify: `.claude/skills/dibels-dashboard/references/model-architecture.md`

- [ ] **Step 1: Update the reference doc**

Add the 4 new models to _Family models_ with 1-line roles. Add a short section
under _Supporting models_: the Benchmark intermediate ports the dashboard's BM
branch, a drift test keeps the 2 in step, and a change to either side's BM logic
must be made to both until the dashboard model reads the facts. State the
2-sitting rule and that it is Anthony's decision.

- [ ] **Step 2: Update the skill**

SKILL.md: 1 row in _Where to look_ for "Changing the dashboard's BM branch or
the Benchmark intermediate", pointing at a new section in
`model-architecture.md`. That section says: edit both, run the drift test, and
never fix a drift failure by loosening the test.

- [ ] **Step 3: Run the layer check**

As PM0's plan Task 3 Step 1 does, with this branch's diff. Expected: no new
violation. The intermediate may read an `int_extracts__` model; a mart may not,
and the 2 dimensions do not.

- [ ] **Step 4: Ask the push question, then push and open the PR**

Ask the Global Constraints question. Push. Open the PR with
`mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`, title
`feat(dbt): DIBELS benchmark expected-tests intermediate and goal dimensions`.
The body gives the row-count reconcile by year, the drift test result, the
2-sitting key count (`<10` where under 10), and says the fact follows on its own
branch once the A12 decision issue is settled. Read the PR back and check it.

- [ ] **Step 5: Offer the follow-ups**

Offer to watch CI and to respond to `claude-review`. On a yes, invoke
`pr-ci-review` and arm a Monitor in that turn.

### Task 5: The Benchmark fact, in dev only

**Files (branch B):**

- Create:
  `src/dbt/kipptaf/models/marts/facts/fct_dibels_benchmark_expected_tests.sql`
- Create:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_dibels_benchmark_expected_tests.yml`

**Interfaces:**

- Consumes: Task 2's intermediate; the 2 dimensions' key recipes from Task 1.
- Produces, for PR PM4:
  - `dibels_benchmark_expected_test_key`: surrogate over the 5 grain columns.
    Primary key.
  - `student_enrollment_key`:
    `{{ student_enrollment_key("student_number", "_dbt_source_project", "academic_year", "entrydate") }}`.
  - `ela_student_section_enrollment_key`:
    `{{ student_section_enrollment_key("ela_section_cc_dcid", "_dbt_source_project", nullable=true) }}`.
  - `dibels_benchmark_school_goal_key` and `dibels_benchmark_region_goal_key`:
    the Task 1 recipes, each wrapped so it is null when the fact's row has no
    matching goal row. Left join the 2 goals models to decide that.
  - `expected_start_date_key`, `expected_end_date_key`, `test_date_key`
    (`client_date`).
  - Degenerate and measure columns: every expected, score, roster and derived
    column from Task 2, with `completed_test_round` as `is_completed_test_round`
    and `measure_standard_score` as `scale_score`.
  - Not carried: `student_number`, `_dbt_source_project`, `entrydate`, `region`,
    `schoolid`, `school`, `grade_level`, `ela_section_cc_dcid`. They are
    reachable through the keys (R9).

- [ ] **Step 1: Write the fact and its yml**

`materialized: table` on the intermediate's cron tick. `primary_key` constraint
and `unique` at `severity: error`. Each key's edge under
`config.meta.foreign_key`, never a `foreign_key` constraint.

- [ ] **Step 2: Build branch A's models and the fact into dev**

Select the 3 Task 1 models, the intermediate and the fact in 1 build. Expected:
all build, all tests pass.

- [ ] **Step 3: Check every key is populated**

1 query: `count(*)`, and `countif(<key> is null)` for each of the 5 keys.
Expected: 0 nulls on `student_enrollment_key`. The section key is null only
where `is_scheduled` is false. The 2 goal keys are null only for a year, region,
school, grade and period with no goal row, and are not null on 99 percent or
more of the rows of a year that has goals.

- [ ] **Step 4: Commit, ask the push question, push**

`git commit -m "feat(dbt): DIBELS benchmark expected-tests fact"`. Push branch
B. Do not open a PR. Tell the user the dev dataset and table name PR PM4 can
read.
