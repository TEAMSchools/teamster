# Year-Grain Cumulative GPA and Needed-GPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add year-by-year cumulative GPA
(`int_powerschool__gpa_cumulative_year`) and needed-weighted-GPA-for-3.0 columns
on `int_powerschool__gpa_cumulative`, per the approved spec
`docs/superpowers/specs/2026-07-02-gpa-cumulative-year-needed-gpa-design.md`
(issue #4295).

**Architecture:** All math lives in the `powerschool` source package. Four
additive columns land inside the existing model's rollup (single source of truth
for the sums). A new year-grain model recomputes completed years from stored Y1
grades and joins the current-year projected point directly from the existing
model — never recomputed (governance invariant). kipptaf gets thin unions in a
second PR after district prod rebuilds (compile-time `union_relations` cannot
see new columns before that).

**Tech Stack:** dbt (BigQuery), dbt unit tests, dbt singular test, Dagster
(auto-materializes district models on merge), dbt Cloud CI (kipptaf only).

## Global Constraints

- Branch for PR 1: `anthonygwalters/feat/claude-gpa-cumulative-year` (exists,
  checked out, holds the spec). PR 1 = `powerschool` package + district
  projects. PR 2 = kipptaf, on a second branch created after PR 1 merges and
  district prod materializes.
- All model changes are **additive-only**; the existing model's grain
  `(studentid, schoolid)` and existing columns are untouched.
- SQL follows `.trunk/config/.sqlfluff`: BigQuery dialect, 88-char lines,
  trailing commas in SELECT, single quotes, lowercase keywords, ST06 column
  ordering (plain refs → literals → simple funcs → nested funcs → logicals).
- Run `/workspaces/teamster/.trunk/tools/trunk check --force <files>` on every
  touched file before pushing — the pre-commit hook only formats.
- Python/dbt always via `uv run`. Never `--target prod` for `dbt build`/`run`
  (classifier-blocked) — dev/staging targets only; prod materialization happens
  via Dagster on merge.
- Dev builds need `--defer --state target/prod` (path relative to
  `--project-dir`).
- The 3.0 threshold is hardcoded into column names/logic by design (KIPP
  policy).
- Paterson disables `int_powerschool__gpa_cumulative`; the new year model must
  be disabled there too (its `ref()` would otherwise fail parse).
- PII: validation results posted anywhere external (PR comments) must be
  aggregates only — row counts, match rates, max abs diff. No student-level
  values.
- `current_academic_year` = 2025 (SY2025-26) at time of writing. Validation
  queries below hardcode 2025; adjust if executing after the July rollover.
- Commit messages: conventional commits, ending with
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

## Task 1: Needed-GPA columns on `int_powerschool__gpa_cumulative`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`

**Interfaces:**

- Consumes: existing model internals (`points_rollup` sums), plus a new
  `gradescale_max` CTE over `int_powerschool__gradescaleitem_lookup`
  (`gradescaleid`, `max(grade_points)`).
- Produces (later tasks rely on these exact names/types):
  `potential_gpa_credits_cum_projected` FLOAT64,
  `potential_gpa_credits_current_year` FLOAT64, `gpa_needed_for_cumulative_3_0`
  FLOAT64, `is_cumulative_3_0_attainable` BOOLEAN.

- [ ] **Step 1: Write the failing unit test**

Append to
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`
(new top-level `unit_tests:` key, below the `models:` block):

```yaml
unit_tests:
  - name: unit_gpa_cumulative_needed_gpa
    description: >-
      Needed-GPA algebra and attainability flag. Student 1 (junior, prior 2.6
      over 70 credits, 35 current credits) needs 3.8. Student 2 (freshman, no
      prior years) needs exactly 3.0. Student 3 (prior 4.2 over 105 credits)
      needs -0.6 — already guaranteed, still attainable. Student 4 (prior 2.0
      over 105 credits) needs 6.0 — above the 4.5 scale max, not attainable.
      Student 5 has no current-year enrollment — needed and flag are NULL.
    model: int_powerschool__gpa_cumulative
    overrides:
      vars:
        current_academic_year: 2025
    given:
      - input: ref('stg_powerschool__storedgrades')
        rows:
          - {
              studentid: 1,
              schoolid: 101,
              course_number: C1,
              academic_year: 2023,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 2.6,
              percent: 80,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 1,
              schoolid: 101,
              course_number: C1,
              academic_year: 2024,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 2.6,
              percent: 80,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 3,
              schoolid: 101,
              course_number: C1,
              academic_year: 2022,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 4.2,
              percent: 95,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 3,
              schoolid: 101,
              course_number: C1,
              academic_year: 2023,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 4.2,
              percent: 95,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 3,
              schoolid: 101,
              course_number: C1,
              academic_year: 2024,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 4.2,
              percent: 95,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 4,
              schoolid: 101,
              course_number: C1,
              academic_year: 2022,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 2.0,
              percent: 80,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 4,
              schoolid: 101,
              course_number: C1,
              academic_year: 2023,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 2.0,
              percent: 80,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 4,
              schoolid: 101,
              course_number: C1,
              academic_year: 2024,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 2.0,
              percent: 80,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 5,
              schoolid: 101,
              course_number: C1,
              academic_year: 2024,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 3.0,
              percent: 85,
              gradescale_name_unweighted: UT Unweighted,
            }
      - input: ref('int_powerschool__gradescaleitem_lookup')
        rows:
          - {
              gradescaleid: 10,
              gradescale_name: UT Weighted,
              letter_grade: A,
              grade_points: 4.5,
              min_cutoffpercentage: 90,
              max_cutoffpercentage: 100,
            }
          - {
              gradescaleid: 10,
              gradescale_name: UT Weighted,
              letter_grade: B,
              grade_points: 3.0,
              min_cutoffpercentage: 80,
              max_cutoffpercentage: 89.9,
            }
          - {
              gradescaleid: 10,
              gradescale_name: UT Weighted,
              letter_grade: F,
              grade_points: 0.0,
              min_cutoffpercentage: 0,
              max_cutoffpercentage: 79.9,
            }
          - {
              gradescaleid: 20,
              gradescale_name: UT Unweighted,
              letter_grade: A,
              grade_points: 4.0,
              min_cutoffpercentage: 90,
              max_cutoffpercentage: 100,
            }
          - {
              gradescaleid: 20,
              gradescale_name: UT Unweighted,
              letter_grade: B,
              grade_points: 3.0,
              min_cutoffpercentage: 80,
              max_cutoffpercentage: 89.9,
            }
          - {
              gradescaleid: 20,
              gradescale_name: UT Unweighted,
              letter_grade: F,
              grade_points: 0.0,
              min_cutoffpercentage: 0,
              max_cutoffpercentage: 79.9,
            }
      - input: ref('base_powerschool__final_grades')
        rows:
          - {
              studentid: 1,
              yearid: 35,
              course_number: C1,
              storecode: Q4,
              exclude_from_gpa: 0,
              termbin_start_date: 2000-01-01,
              termbin_end_date: 9999-12-31,
              potential_credit_hours: 35.0,
              y1_letter_grade: B,
              y1_grade_points: 3.0,
              y1_grade_points_unweighted: 3.0,
              courses_gradescaleid: 10,
            }
          - {
              studentid: 2,
              yearid: 35,
              course_number: C1,
              storecode: Q4,
              exclude_from_gpa: 0,
              termbin_start_date: 2000-01-01,
              termbin_end_date: 9999-12-31,
              potential_credit_hours: 35.0,
              y1_letter_grade: B,
              y1_grade_points: 3.0,
              y1_grade_points_unweighted: 3.0,
              courses_gradescaleid: 10,
            }
          - {
              studentid: 3,
              yearid: 35,
              course_number: C1,
              storecode: Q4,
              exclude_from_gpa: 0,
              termbin_start_date: 2000-01-01,
              termbin_end_date: 9999-12-31,
              potential_credit_hours: 35.0,
              y1_letter_grade: B,
              y1_grade_points: 3.0,
              y1_grade_points_unweighted: 3.0,
              courses_gradescaleid: 10,
            }
          - {
              studentid: 4,
              yearid: 35,
              course_number: C1,
              storecode: Q4,
              exclude_from_gpa: 0,
              termbin_start_date: 2000-01-01,
              termbin_end_date: 9999-12-31,
              potential_credit_hours: 35.0,
              y1_letter_grade: B,
              y1_grade_points: 3.0,
              y1_grade_points_unweighted: 3.0,
              courses_gradescaleid: 10,
            }
      - input: ref('base_powerschool__student_enrollments')
        rows:
          - {
              studentid: 1,
              yearid: 35,
              academic_year: 2025,
              schoolid: 101,
              rn_year: 1,
            }
          - {
              studentid: 2,
              yearid: 35,
              academic_year: 2025,
              schoolid: 101,
              rn_year: 1,
            }
          - {
              studentid: 3,
              yearid: 35,
              academic_year: 2025,
              schoolid: 101,
              rn_year: 1,
            }
          - {
              studentid: 4,
              yearid: 35,
              academic_year: 2025,
              schoolid: 101,
              rn_year: 1,
            }
    expect:
      rows:
        - {
            studentid: 1,
            potential_gpa_credits_current_year: 35.0,
            gpa_needed_for_cumulative_3_0: 3.8,
            is_cumulative_3_0_attainable: true,
          }
        - {
            studentid: 2,
            potential_gpa_credits_current_year: 35.0,
            gpa_needed_for_cumulative_3_0: 3.0,
            is_cumulative_3_0_attainable: true,
          }
        - {
            studentid: 3,
            potential_gpa_credits_current_year: 35.0,
            gpa_needed_for_cumulative_3_0: -0.6,
            is_cumulative_3_0_attainable: true,
          }
        - {
            studentid: 4,
            potential_gpa_credits_current_year: 35.0,
            gpa_needed_for_cumulative_3_0: 6.0,
            is_cumulative_3_0_attainable: false,
          }
        - {
            studentid: 5,
            potential_gpa_credits_current_year: null,
            gpa_needed_for_cumulative_3_0: null,
            is_cumulative_3_0_attainable: null,
          }
```

Hand-check of expectations: student 1 needs
`(3.0 * (70 + 35) - 182) / 35 = 3.8`; student 3 `(420 - 441) / 35 = -0.6`;
student 4 `(420 - 210) / 35 = 6.0` vs. scale max `4.5` → false.

- [ ] **Step 2: Run the unit test to verify it fails**

```bash
uv run dbt test --select "int_powerschool__gpa_cumulative,test_type:unit" \
  --project-dir src/dbt/kippnewark --defer --state target/prod --target dev
```

Expected: FAIL — the expect columns (`gpa_needed_for_cumulative_3_0`, etc.)
don't exist on the model yet, so the test errors with an unrecognized-column
compilation error. (If this is the first dbt run in a fresh worktree, run
`uv run dbt deps --project-dir src/dbt/kippnewark` first. Dict-format fixtures
introspect upstream relations via the defer manifest — prod relations exist, so
introspection succeeds.)

- [ ] **Step 3: Implement the SQL changes**

Apply these five edits to
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`:

**Edit 3a** — add a `gradescale_max` CTE as the first CTE. Replace:

```sql
with
    grades_union as (
```

with:

```sql
with
    gradescale_max as (
        select gradescaleid, max(grade_points) as max_grade_points,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        group by gradescaleid
    ),

    grades_union as (
```

**Edit 3b** — branch 1 (stored grades): append one column at the end of the
branch's SELECT, immediately after the
`... as unweighted_grade_points_projected,` line (before
`from {{ ref("stg_powerschool__storedgrades") }} as sg`):

```sql
            if(
                sg.excludefromgpa = 0, sg.gpa_points, null
            ) as gpa_points_projected_max,
```

**Edit 3c** — branch 2 (current-year in-progress): two changes. Append at the
end of that branch's SELECT, after
`fg.y1_grade_points_unweighted as unweighted_grade_points_projected,`:

```sql
            if(
                fg.y1_letter_grade is null, null, gsm.max_grade_points
            ) as gpa_points_projected_max,
```

and add a join after that branch's
`left join {{ ref("stg_powerschool__storedgrades") }} as sg ... and sg.storecode = 'Y1'`
lines (before the branch's `where`):

```sql
        left join gradescale_max as gsm on fg.courses_gradescaleid = gsm.gradescaleid
```

**Edit 3d** — branch 3 (S1 as of Q2): append at the end of that branch's SELECT,
after `null as unweighted_grade_points_projected,`:

```sql
            null as gpa_points_projected_max,
```

(The new column must be the last column in all three UNION ALL branches —
`union all` matches by position.)

**Edit 3e** — in the `with_weighted_points` CTE, append after
`(potentialcrhrs_projected * unweighted_grade_points_projected) as weighted_points_projected_unweighted,`:

```sql
            (
                potentialcrhrs_projected * gpa_points_projected_max
            ) as weighted_points_projected_max,
```

**Edit 3f** — in `points_rollup`, append after the
`sum(if(academic_year < ..., earnedcrhrs, potentialcrhrs)) as potential_credits_cum,`
block:

```sql
            sum(
                if(
                    academic_year < {{ var("current_academic_year") }},
                    weighted_points,
                    null
                )
            ) as weighted_points_prior,
            sum(
                if(
                    academic_year < {{ var("current_academic_year") }},
                    potentialcrhrs,
                    null
                )
            ) as potentialcrhrs_prior,
            sum(
                if(
                    academic_year = {{ var("current_academic_year") }},
                    potentialcrhrs_projected,
                    null
                )
            ) as potentialcrhrs_current,
            sum(
                if(
                    academic_year = {{ var("current_academic_year") }},
                    weighted_points_projected_max,
                    null
                )
            ) as weighted_points_projected_max_current,
```

**Edit 3g** — insert a `needed_gpa` CTE between `points_rollup` and the final
SELECT, and reroute the final SELECT. Replace:

```sql
        from with_weighted_points
        group by studentid, schoolid
    )

select
```

with:

```sql
        from with_weighted_points
        group by studentid, schoolid
    ),

    needed_gpa as (
        select
            *,

            safe_divide(
                (
                    3.0
                    * (coalesce(potentialcrhrs_prior, 0) + potentialcrhrs_current)
                )
                - coalesce(weighted_points_prior, 0),
                potentialcrhrs_current
            ) as gpa_needed_raw,

            safe_divide(
                weighted_points_projected_max_current, potentialcrhrs_current
            ) as gpa_max_current_raw,
        from points_rollup
    )

select
```

Then in the final SELECT: add two plain-ref outputs after
`earned_credits_cum_projected_s1,`:

```sql
    potentialcrhrs_projected as potential_gpa_credits_cum_projected,
    potentialcrhrs_current as potential_gpa_credits_current_year,
```

append after the `core_cumulative_y1_gpa` round expression:

```sql
    round(gpa_needed_raw, 2) as gpa_needed_for_cumulative_3_0,

    round(gpa_needed_raw, 2)
    <= round(gpa_max_current_raw, 2) as is_cumulative_3_0_attainable,
```

and change the final `from points_rollup` to `from needed_gpa`.

Notes on the logic:

- `coalesce(..., 0)` on the prior sums makes the freshman case collapse to
  exactly 3.0; `potentialcrhrs_current` stays un-coalesced so `safe_divide`
  returns NULL when the student has no current-year GPA credits.
- The flag compares displayed (2-decimal) values so it never contradicts what
  users see; NULL on either side propagates to NULL.
- `gpa_points_projected_max` is the actual points for already-stored
  current-year rows (locked in) and the scale max for in-progress rows, so the
  attainability ceiling is exact mid-year and after partial stores.

- [ ] **Step 4: Add the four columns to the package properties YAML**

Append to the `columns:` list of
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`:

```yaml
- name: potential_gpa_credits_cum_projected
  data_type: float64
  description: >-
    Sum of potential GPA credit hours across all years, including in-progress
    current-year courses — the denominator behind `cumulative_y1_gpa_projected`,
    exposed so the projected ratio is auditable and joinable downstream.
- name: potential_gpa_credits_current_year
  data_type: float64
  description: >-
    Potential GPA credit hours the student is enrolled in for the current
    academic year (in-progress courses with a Y1 grade plus any already-stored
    current-year courses). NULL when the student has no current-year GPA
    credits.
- name: gpa_needed_for_cumulative_3_0
  data_type: float64
  description: >-
    Weighted Y1 GPA the student must average across all current-year GPA credits
    to finish with a projected cumulative Y1 GPA of exactly 3.00. Computed as
    (3.0 x (prior credits + current credits) - prior weighted points) / current
    credits. Assumes the current credit denominator stays fixed — course
    adds/drops move the target. Negative values mean 3.00 is already guaranteed;
    values above the student's scale maximum are not attainable this year. NULL
    when the student has no current-year GPA credits.
- name: is_cumulative_3_0_attainable
  data_type: boolean
  description: >-
    True when `gpa_needed_for_cumulative_3_0` is less than or equal to the
    credit-weighted maximum weighted GPA achievable across the student's
    current-year courses (each in-progress course capped at the max grade points
    of its weighted grade scale; already-stored current-year grades locked at
    their actual points). NULL when the needed value is NULL.
```

- [ ] **Step 5: Run the unit test to verify it passes**

```bash
uv run dbt test --select "int_powerschool__gpa_cumulative,test_type:unit" \
  --project-dir src/dbt/kippnewark --defer --state target/prod --target dev
```

Expected: PASS (1 unit test).

- [ ] **Step 6: Build the model to the dev schema**

```bash
uv run dbt build --select int_powerschool__gpa_cumulative \
  --project-dir src/dbt/kippnewark --defer --state target/prod --target dev
```

Expected: model builds to `zz_<GITHUB_USER>_kippnewark_powerschool`
(`zz_anthonygwalters_kippnewark_powerschool` in this environment — confirm the
dataset name in the build log) with the unit test passing first. This dev
relation also unblocks Task 2's unit-test introspection of the new columns.

- [ ] **Step 7: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml
git -C /workspaces/teamster add \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml
git -C /workspaces/teamster commit \
  -m "feat(powerschool): add needed-GPA-for-3.0 columns to int_powerschool__gpa_cumulative" \
  -m "Refs #4295" \
  -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: trunk reports no issues; commit succeeds.

---

## Task 2: New model `int_powerschool__gpa_cumulative_year`

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative_year.yml`
- Modify: `src/dbt/kipppaterson/dbt_project.yml`

**Interfaces:**

- Consumes: `stg_powerschool__storedgrades`,
  `int_powerschool__gradescaleitem_lookup`,
  `base_powerschool__student_enrollments` (`rn_year = 1` rows), and Task 1's
  `int_powerschool__gpa_cumulative` columns (`cumulative_y1_gpa_projected`,
  `cumulative_y1_gpa_projected_unweighted`, `earned_credits_cum_projected`,
  `potential_gpa_credits_cum_projected`).
- Produces: grain `(studentid, schoolid, academic_year)` with columns
  `studentid` INT64, `schoolid` INT64, `academic_year` INT64, `grade_level`
  INT64, `earned_credits_cum` FLOAT64, `potential_gpa_credits_cum` FLOAT64,
  `cumulative_y1_gpa` FLOAT64, `cumulative_y1_gpa_unweighted` FLOAT64,
  `is_projected` BOOLEAN. Task 3's singular test and Task 7's kipptaf union
  depend on these exact names.

- [ ] **Step 1: Write the properties YAML with the failing unit test**

Create
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative_year.yml`:

```yaml
models:
  - name: int_powerschool__gpa_cumulative_year
    description: >-
      One row per student, school, and academic year holding the student's
      cumulative Y1 GPA as of the end of that year. Completed years are
      recomputed from stored Y1 grades as running sums per student-school; the
      current academic year is a projected point joined directly from
      int_powerschool__gpa_cumulative (never recomputed), flagged with
      is_projected. Accumulation is per student-school, matching
      int_powerschool__gpa_cumulative — middle school and high school series
      stay separate, and school transfers split the series.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - schoolid
              - academic_year
          config:
            severity: error
    columns:
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: schoolid
        data_type: int64
        description: >-
          School_Number of the school where the grades were stored (completed
          years) or where the student is currently enrolled (projected row).
      - name: academic_year
        data_type: int64
        description: >-
          Academic year the cumulative values run through — start-year
          convention (2024 means SY2024-25).
      - name: grade_level
        data_type: int64
        description: >-
          Student's grade level in that academic year, from the year's primary
          enrollment. NULL for stored years with no matching enrollment (e.g.
          transfer credits). A retained student legitimately repeats a grade
          level across two academic years.
      - name: earned_credits_cum
        data_type: float64
        description: >-
          Running earned credit hours through this academic year
          (graduation-credit basis, excludefromgraduation = 0). Projected basis
          on the current-year row.
      - name: potential_gpa_credits_cum
        data_type: float64
        description: >-
          Running potential GPA credit hours through this academic year (GPA
          basis, excludefromgpa = 0) — the denominator of the cumulative GPAs.
      - name: cumulative_y1_gpa
        data_type: float64
        description: >-
          Cumulative weighted Y1 GPA through this academic year. On the
          current-year row this is cumulative_y1_gpa_projected from
          int_powerschool__gpa_cumulative, verbatim.
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
        description: >-
          Cumulative unweighted Y1 GPA through this academic year. On the
          current-year row this is cumulative_y1_gpa_projected_unweighted from
          int_powerschool__gpa_cumulative, verbatim.
      - name: is_projected
        data_type: boolean
        description: >-
          False for completed years recomputed from stored grades; true for the
          current-year row sourced from projected values.

unit_tests:
  - name: unit_gpa_cumulative_year_running_and_projected
    description: >-
      Running cumulative accumulates stored Y1 grades per student-school in
      academic-year order (excluded-from-GPA rows drop out of both bases), and
      the current-year row carries the projected values from
      int_powerschool__gpa_cumulative verbatim with is_projected = true.
    model: int_powerschool__gpa_cumulative_year
    overrides:
      vars:
        current_academic_year: 2025
    given:
      - input: ref('stg_powerschool__storedgrades')
        rows:
          - {
              studentid: 1,
              schoolid: 101,
              academic_year: 2023,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 2.0,
              percent: 70,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 1,
              schoolid: 101,
              academic_year: 2024,
              storecode: Y1,
              excludefromgpa: 0,
              excludefromgraduation: 0,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 4.0,
              percent: 95,
              gradescale_name_unweighted: UT Unweighted,
            }
          - {
              studentid: 1,
              schoolid: 101,
              academic_year: 2024,
              storecode: Y1,
              excludefromgpa: 1,
              excludefromgraduation: 1,
              potentialcrhrs: 35.0,
              earnedcrhrs: 35.0,
              gpa_points: 1.0,
              percent: 50,
              gradescale_name_unweighted: UT Unweighted,
            }
      - input: ref('int_powerschool__gradescaleitem_lookup')
        rows:
          - {
              gradescaleid: 20,
              gradescale_name: UT Unweighted,
              letter_grade: A,
              grade_points: 4.0,
              min_cutoffpercentage: 90,
              max_cutoffpercentage: 100,
            }
          - {
              gradescaleid: 20,
              gradescale_name: UT Unweighted,
              letter_grade: F,
              grade_points: 0.0,
              min_cutoffpercentage: 0,
              max_cutoffpercentage: 89.9,
            }
      - input: ref('base_powerschool__student_enrollments')
        rows:
          - {
              studentid: 1,
              schoolid: 101,
              academic_year: 2023,
              rn_year: 1,
              grade_level: 9,
            }
          - {
              studentid: 1,
              schoolid: 101,
              academic_year: 2024,
              rn_year: 1,
              grade_level: 10,
            }
          - {
              studentid: 1,
              schoolid: 101,
              academic_year: 2025,
              rn_year: 1,
              grade_level: 11,
            }
      - input: ref('int_powerschool__gpa_cumulative')
        rows:
          - {
              studentid: 1,
              schoolid: 101,
              cumulative_y1_gpa_projected: 3.2,
              cumulative_y1_gpa_projected_unweighted: 2.5,
              earned_credits_cum_projected: 105.0,
              potential_gpa_credits_cum_projected: 105.0,
            }
    expect:
      rows:
        - {
            studentid: 1,
            academic_year: 2023,
            grade_level: 9,
            earned_credits_cum: 35.0,
            potential_gpa_credits_cum: 35.0,
            cumulative_y1_gpa: 2.0,
            cumulative_y1_gpa_unweighted: 0.0,
            is_projected: false,
          }
        - {
            studentid: 1,
            academic_year: 2024,
            grade_level: 10,
            earned_credits_cum: 70.0,
            potential_gpa_credits_cum: 70.0,
            cumulative_y1_gpa: 3.0,
            cumulative_y1_gpa_unweighted: 2.0,
            is_projected: false,
          }
        - {
            studentid: 1,
            academic_year: 2025,
            grade_level: 11,
            earned_credits_cum: 105.0,
            potential_gpa_credits_cum: 105.0,
            cumulative_y1_gpa: 3.2,
            cumulative_y1_gpa_unweighted: 2.5,
            is_projected: true,
          }
```

Hand-check: 2023 row `70 / 35 = 2.0` weighted, `0 / 35 = 0.0` unweighted
(percent 70 maps to F); 2024 row `(70 + 140) / 70 = 3.0` weighted,
`140 / 70 = 2.0` unweighted (the excluded row contributes nothing to either
basis); 2025 row is the mocked projected values verbatim.

- [ ] **Step 2: Run the unit test to verify it fails**

```bash
uv run dbt test --select "int_powerschool__gpa_cumulative_year,test_type:unit" \
  --project-dir src/dbt/kippnewark --defer --state target/prod --target dev
```

Expected: FAIL — compilation error, the model
`int_powerschool__gpa_cumulative_year` does not exist yet.

- [ ] **Step 3: Write the model SQL**

Create
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql`:

```sql
with
    stored_grades as (
        select
            sg.studentid,
            sg.schoolid,
            sg.academic_year,

            if(sg.excludefromgpa = 0, sg.potentialcrhrs, null) as potentialcrhrs,
            if(sg.excludefromgraduation = 0, sg.earnedcrhrs, null) as earnedcrhrs,
            if(sg.excludefromgpa = 0, sg.gpa_points, null) as gpa_points,
            if(
                sg.excludefromgpa = 0, su.grade_points, null
            ) as unweighted_grade_points,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as su
            on sg.percent between su.min_cutoffpercentage and su.max_cutoffpercentage
            and sg.gradescale_name_unweighted = su.gradescale_name
        where
            sg.storecode = 'Y1'
            and sg.academic_year < {{ var("current_academic_year") }}
    ),

    year_rollup as (
        select
            studentid,
            schoolid,
            academic_year,

            sum(potentialcrhrs * gpa_points) as weighted_points,
            sum(potentialcrhrs * unweighted_grade_points) as unweighted_points,
            sum(potentialcrhrs) as potential_gpa_credits,
            sum(earnedcrhrs) as earned_credits,
        from stored_grades
        group by studentid, schoolid, academic_year
    ),

    running_totals as (
        select
            studentid,
            schoolid,
            academic_year,

            sum(weighted_points) over (
                partition by studentid, schoolid order by academic_year
            ) as weighted_points_cum,
            sum(unweighted_points) over (
                partition by studentid, schoolid order by academic_year
            ) as unweighted_points_cum,
            sum(potential_gpa_credits) over (
                partition by studentid, schoolid order by academic_year
            ) as potential_gpa_credits_cum,
            sum(earned_credits) over (
                partition by studentid, schoolid order by academic_year
            ) as earned_credits_cum,
        from year_rollup
    ),

    completed_years as (
        select
            rt.studentid,
            rt.schoolid,
            rt.academic_year,
            rt.earned_credits_cum,
            rt.potential_gpa_credits_cum,

            enr.grade_level,

            false as is_projected,

            round(
                safe_divide(rt.weighted_points_cum, rt.potential_gpa_credits_cum), 2
            ) as cumulative_y1_gpa,
            round(
                safe_divide(rt.unweighted_points_cum, rt.potential_gpa_credits_cum),
                2
            ) as cumulative_y1_gpa_unweighted,
        from running_totals as rt
        left join
            {{ ref("base_powerschool__student_enrollments") }} as enr
            on rt.studentid = enr.studentid
            and rt.academic_year = enr.academic_year
            and enr.rn_year = 1
    ),

    projected_current_year as (
        select
            gc.studentid,
            gc.schoolid,
            gc.earned_credits_cum_projected as earned_credits_cum,
            gc.potential_gpa_credits_cum_projected as potential_gpa_credits_cum,
            gc.cumulative_y1_gpa_projected as cumulative_y1_gpa,

            enr.grade_level,

            {{ var("current_academic_year") }} as academic_year,
            true as is_projected,

            gc.cumulative_y1_gpa_projected_unweighted
            as cumulative_y1_gpa_unweighted,
        from {{ ref("int_powerschool__gpa_cumulative") }} as gc
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as enr
            on gc.studentid = enr.studentid
            and gc.schoolid = enr.schoolid
            and enr.academic_year = {{ var("current_academic_year") }}
            and enr.rn_year = 1
    )

select
    studentid,
    schoolid,
    academic_year,
    grade_level,
    earned_credits_cum,
    potential_gpa_credits_cum,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    is_projected,
from completed_years

union all

select
    studentid,
    schoolid,
    academic_year,
    grade_level,
    earned_credits_cum,
    potential_gpa_credits_cum,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    is_projected,
from projected_current_year
```

Notes:

- The `stored_grades` filters replicate the existing model's stored branch
  exactly (same exclusion flags, same unweighted lookup join) — this is what
  makes Task 3's reconciliation test exact.
- `academic_year < current` keeps the recompute and the joined projected row
  disjoint, so the composite PK holds without deduplication.
- The projected branch is an INNER join to current-year enrollment: students not
  currently enrolled get no projected row; a student whose original-model row
  exists at a different school than their current enrollment gets no projected
  row at the new school (no grades there yet — nothing to project).
- The window running sums use the default frame (unbounded preceding to current
  row); `academic_year` is unique within each partition after `year_rollup`, so
  the result is deterministic.

- [ ] **Step 4: Run the unit test to verify it passes, then build**

```bash
uv run dbt build --select int_powerschool__gpa_cumulative_year \
  --project-dir src/dbt/kippnewark --defer --state target/prod --target dev
```

Expected: unit test PASS, model builds, uniqueness test PASS. (`dbt build` runs
the unit test before materializing. The `int_powerschool__gpa_cumulative` input
introspects the dev relation built in Task 1 Step 6, which already has the new
columns.)

- [ ] **Step 5: Disable the model in Paterson**

In `src/dbt/kipppaterson/dbt_project.yml`, locate:

```yaml
int_powerschool__gpa_cumulative:
  +enabled: false
```

and add immediately after it (same indentation level):

```yaml
int_powerschool__gpa_cumulative_year:
  +enabled: false
```

- [ ] **Step 6: Verify Paterson still parses and excludes the model**

```bash
uv run dbt parse --project-dir src/dbt/kipppaterson
uv run dbt ls --select int_powerschool__gpa_cumulative_year \
  --project-dir src/dbt/kipppaterson
```

Expected: parse succeeds with no errors; `dbt ls` reports the selector matches
no enabled nodes (warning "Nothing to do" or an empty list).

- [ ] **Step 7: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative_year.yml \
  src/dbt/kipppaterson/dbt_project.yml
git -C /workspaces/teamster add \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative_year.yml \
  src/dbt/kipppaterson/dbt_project.yml
git -C /workspaces/teamster commit \
  -m "feat(powerschool): add int_powerschool__gpa_cumulative_year" \
  -m "Year-grain cumulative GPA - completed years recomputed from stored Y1 grades, current year joined from int_powerschool__gpa_cumulative projected columns. Disabled in kipppaterson alongside its parent. Refs #4295" \
  -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: trunk clean; commit succeeds.

---

## Task 3: Reconciliation singular test

**Files:**

- Create:
  `src/dbt/powerschool/tests/test_int_powerschool__gpa_cumulative_year__reconciles_stored.sql`
- Modify: `src/dbt/powerschool/tests/properties.yml`

**Interfaces:**

- Consumes: Task 2's model output (`is_projected`, `cumulative_y1_gpa`,
  `cumulative_y1_gpa_unweighted`) and the existing model's stored-only columns.
- Produces: a warn-severity drift guard that runs with every district build.

- [ ] **Step 1: Write the singular test**

Create
`src/dbt/powerschool/tests/test_int_powerschool__gpa_cumulative_year__reconciles_stored.sql`:

```sql
with
    latest_stored as (
        select
            studentid,
            schoolid,
            academic_year,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,
        from {{ ref("int_powerschool__gpa_cumulative_year") }}
        where not is_projected
        qualify
            row_number() over (
                partition by studentid, schoolid order by academic_year desc
            )
            = 1
    )

select
    ls.studentid,
    ls.schoolid,
    ls.academic_year,
    ls.cumulative_y1_gpa,
    ls.cumulative_y1_gpa_unweighted,

    gc.cumulative_y1_gpa as gpa_cumulative_weighted,
    gc.cumulative_y1_gpa_unweighted as gpa_cumulative_unweighted,
from latest_stored as ls
inner join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on ls.studentid = gc.studentid
    and ls.schoolid = gc.schoolid
where
    not exists (
        select 1
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        where
            ls.studentid = sg.studentid
            and ls.schoolid = sg.schoolid
            and sg.storecode = 'Y1'
            and sg.academic_year = {{ var("current_academic_year") }}
    )
    and (
        abs(
            coalesce(ls.cumulative_y1_gpa, -99)
            - coalesce(gc.cumulative_y1_gpa, -99)
        )
        > 0.01
        or abs(
            coalesce(ls.cumulative_y1_gpa_unweighted, -99)
            - coalesce(gc.cumulative_y1_gpa_unweighted, -99)
        )
        > 0.01
    )
```

(The `not exists` excludes student-schools that already have stored current-year
Y1 grades — once those store, the original model includes them and the latest
completed-year row is no longer the same quantity. The `qualify row_number` here
picks the latest row of a series for comparison — it is not a dedup mask.)

- [ ] **Step 2: Register the test description and Dagster ref**

Append to `src/dbt/powerschool/tests/properties.yml` under the existing
`data_tests:` key:

```yaml
- name: test_int_powerschool__gpa_cumulative_year__reconciles_stored
  description: >-
    Drift guard for the year-grain recompute — for each student-school, the
    latest completed-year row of int_powerschool__gpa_cumulative_year must match
    int_powerschool__gpa_cumulative within 0.01 on both weighted and unweighted
    cumulative GPA, for students with no stored current-year Y1 grades (once
    current-year grades store, the original model includes them and the
    comparison is no longer like-for-like). Identical filters and rounding make
    this exact in practice; the 0.01 tolerance absorbs float summation-order
    noise at rounding boundaries. Runs at the project default warn severity so a
    transient discrepancy surfaces without blocking district prod builds —
    investigate any warning immediately.
  config:
    meta:
      dagster:
        ref:
          name: int_powerschool__gpa_cumulative_year
          package: powerschool
```

- [ ] **Step 3: Run the test**

```bash
uv run dbt test \
  --select test_int_powerschool__gpa_cumulative_year__reconciles_stored \
  --project-dir src/dbt/kippnewark --defer --state target/prod --target dev
```

Expected: PASS with 0 failing rows (both models were built to the dev schema in
Tasks 1-2 from the same prod source data). If rows return, debug before
proceeding — the recompute filters have drifted from the stored branch.

- [ ] **Step 4: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/powerschool/tests/test_int_powerschool__gpa_cumulative_year__reconciles_stored.sql \
  src/dbt/powerschool/tests/properties.yml
git -C /workspaces/teamster add \
  src/dbt/powerschool/tests/test_int_powerschool__gpa_cumulative_year__reconciles_stored.sql \
  src/dbt/powerschool/tests/properties.yml
git -C /workspaces/teamster commit \
  -m "test(powerschool): reconcile gpa_cumulative_year stored rows against gpa_cumulative" \
  -m "Refs #4295" \
  -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: trunk clean; commit succeeds.

---

## Task 4: Full dev builds in Camden and Miami

**Files:** none (validation only; Newark already built in Tasks 1-3).

- [ ] **Step 1: Build both models plus tests in Camden**

```bash
uv run dbt build \
  --select int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year \
  --project-dir src/dbt/kippcamden --defer --state target/prod --target dev
```

Expected: unit tests, both models, uniqueness test, and the reconciliation test
all PASS. (Run `uv run dbt deps --project-dir src/dbt/kippcamden` first if
packages are missing.)

- [ ] **Step 2: Build both models plus tests in Miami**

```bash
uv run dbt build \
  --select int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year \
  --project-dir src/dbt/kippmiami --defer --state target/prod --target dev
```

Expected: same — all PASS.

No commit — this task produces no file changes; it gates Task 5.

---

## Task 5: Prod-data reconciliation validation and PR 1 handoff

**Files:** none (BigQuery validation + PR metadata).

This is the user-required validation: **compare the year model's current-year
rows to the original int model's values on prod data.** The dev builds read prod
sources via `--defer`, so dev outputs are prod-data-derived.

- [ ] **Step 1: Projected-row reconciliation, per district**

Run via BigQuery MCP for each district (substitute `kippcamden` / `kippmiami`
for `kippnewark`; dev dataset prefix is `zz_<GITHUB_USER>_`, i.e.
`zz_anthonygwalters_` in this environment):

```sql
select
    count(*) as n_projected_rows,
    countif(gc.studentid is null) as n_unjoined,
    countif(
        y.cumulative_y1_gpa is distinct from gc.cumulative_y1_gpa_projected
    ) as n_weighted_mismatch,
    countif(
        y.cumulative_y1_gpa_unweighted
        is distinct from gc.cumulative_y1_gpa_projected_unweighted
    ) as n_unweighted_mismatch,
from `teamster-332318.zz_anthonygwalters_kippnewark_powerschool.int_powerschool__gpa_cumulative_year` as y
left join
    `teamster-332318.zz_anthonygwalters_kippnewark_powerschool.int_powerschool__gpa_cumulative` as gc
    on y.studentid = gc.studentid
    and y.schoolid = gc.schoolid
where y.is_projected
```

Expected: `n_unjoined = 0`, `n_weighted_mismatch = 0`,
`n_unweighted_mismatch = 0` in every district — the values are joined, so any
mismatch is a join bug (wrong school matched), not a math bug.

- [ ] **Step 2: Stored-row count spot check, per district**

```sql
select
    (
        select count(*)
        from
            `teamster-332318.zz_anthonygwalters_kippnewark_powerschool.int_powerschool__gpa_cumulative_year`
        where not is_projected
    ) as n_model_stored_rows,
    (
        select
            count(distinct concat(studentid, '|', schoolid, '|', academic_year))
        from `teamster-332318.kippnewark_powerschool.stg_powerschool__storedgrades`
        where storecode = 'Y1' and academic_year < 2025
    ) as n_expected_rows
```

Expected: the two counts are equal (the recompute keeps one row per
student-school-year of stored Y1 grades, including years whose courses are all
GPA-excluded).

- [ ] **Step 3: Post aggregate results to PR 4296 and mark it ready**

Post a comment on PR #4296 with the per-district aggregate tables from Steps 1-2
(counts and match rates ONLY — no student-level values), note that the
reconciliation singular test passed in all three districts, then update the PR:
refresh the body's summary line to say the implementation is included (drop
"design spec only"), and clear the draft flag via
`mcp__github__update_pull_request` with `draft: false`.

- [ ] **Step 4: Push and hand off for review/merge**

```bash
git -C /workspaces/teamster push origin anthonygwalters/feat/claude-gpa-cumulative-year
```

Expected: Trunk CI passes; dbt Cloud CI is a no-op (no kipptaf models modified —
per repo convention that green is not evidence for district changes, which is
why Tasks 1-4's local builds are the real gate). The user reviews and
squash-merges PR 1. On merge, each district's `deploy-prod-<location>.yaml`
fires (all four list `src/dbt/powerschool/**`) and Dagster materializes the
new/changed models in prod.

---

## Task 6: Post-merge gate — verify district prod materialized

**Files:** none. Do not start PR 2 work until this gate passes.

- [ ] **Step 1: Confirm deploys ran**

```bash
gh run list --branch main --limit 8
```

Expected: `deploy-prod-kippnewark`, `deploy-prod-kippcamden`,
`deploy-prod-kippmiami` (and `kipppaterson`) runs for the merge commit, all
successful.

- [ ] **Step 2: Confirm the new model materialized in each district**

Preferred: `mcp__dagster__get_asset_materializations` for asset keys
`kippnewark/powerschool/int_powerschool__gpa_cumulative_year`,
`kippcamden/powerschool/int_powerschool__gpa_cumulative_year`,
`kippmiami/powerschool/int_powerschool__gpa_cumulative_year` — each must show a
materialization after the merge time. Also confirm
`.../int_powerschool__gpa_cumulative` re-materialized (its contract now includes
the four new columns).

Fallback via BigQuery MCP:

```sql
select table_id, timestamp_millis(last_modified_time) as last_modified,
from `teamster-332318.kippnewark_powerschool.__TABLES__`
where table_id in (
    'int_powerschool__gpa_cumulative', 'int_powerschool__gpa_cumulative_year'
)
```

Expected: both tables exist with `last_modified` after the merge, in all three
districts.

---

## Task 7: PR 2 — kipptaf unions and column exposure

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_cumulative_year.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative_year.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative.yml`

**Interfaces:**

- Consumes: district prod tables from Task 6; Task 2's column list.
- Produces: kipptaf-level `int_powerschool__gpa_cumulative_year` (district
  columns + `_dbt_source_relation` + `_dbt_source_project`), and the four
  needed-GPA columns visible on the kipptaf `int_powerschool__gpa_cumulative`.

- [ ] **Step 1: Create the PR 2 branch (linked to #4295)**

```bash
git -C /workspaces/teamster checkout main
git -C /workspaces/teamster pull
gh issue develop 4295 --name anthonygwalters/feat/claude-gpa-year-kipptaf --checkout
```

Expected: new branch created from current `main` and checked out.

- [ ] **Step 2: Add the source table entries (all three districts)**

In each of `sources-kippnewark.yml`, `sources-kippcamden.yml`,
`sources-kippmiami.yml` under `src/dbt/kipptaf/models/powerschool/`, insert
immediately after the existing `int_powerschool__gpa_cumulative` entry (keeping
the file's ordering), with the district name swapped per file — Newark shown:

```yaml
- name: int_powerschool__gpa_cumulative_year
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - kippnewark
          - powerschool
          - int_powerschool__gpa_cumulative_year
```

- [ ] **Step 3: Create the kipptaf union model**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_cumulative_year.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select
    ur.*,

    {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
```

- [ ] **Step 4: Create the kipptaf properties YAML**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative_year.yml`:

```yaml
models:
  - name: int_powerschool__gpa_cumulative_year
    description: >-
      Network union of the district int_powerschool__gpa_cumulative_year models
      (Newark, Camden, Miami) — one row per student, school, and academic year
      with cumulative Y1 GPA as of the end of that year; current-year rows are
      projected (is_projected = true) and match int_powerschool__gpa_cumulative
      projected values exactly.
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - _dbt_source_relation
              - studentid
              - schoolid
              - academic_year
    columns:
      - name: _dbt_source_relation
        data_type: string
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: schoolid
        data_type: int64
        description: >-
          School_Number of the school where the grades were stored (completed
          years) or where the student is currently enrolled (projected row).
      - name: academic_year
        data_type: int64
        description: >-
          Academic year the cumulative values run through — start-year
          convention (2024 means SY2024-25).
      - name: grade_level
        data_type: int64
        description: >-
          Student's grade level in that academic year, from the year's primary
          enrollment. NULL for stored years with no matching enrollment.
      - name: earned_credits_cum
        data_type: float64
        description: >-
          Running earned credit hours through this academic year
          (graduation-credit basis). Projected basis on the current-year row.
      - name: potential_gpa_credits_cum
        data_type: float64
        description: >-
          Running potential GPA credit hours through this academic year — the
          denominator of the cumulative GPAs.
      - name: cumulative_y1_gpa
        data_type: float64
        description: >-
          Cumulative weighted Y1 GPA through this academic year. On the
          current-year row this matches cumulative_y1_gpa_projected verbatim.
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
        description: >-
          Cumulative unweighted Y1 GPA through this academic year. On the
          current-year row this matches cumulative_y1_gpa_projected_unweighted
          verbatim.
      - name: is_projected
        data_type: boolean
        description: >-
          False for completed years recomputed from stored grades; true for the
          current-year row sourced from projected values.
      - name: _dbt_source_project
        data_type: string
        description: District code location derived from `_dbt_source_relation`.
```

- [ ] **Step 5: Expose the four new columns on the existing kipptaf union YAML**

Append to the `columns:` list in
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative.yml`
(before the `_dbt_source_project` entry, keeping district columns grouped ahead
of the kipptaf-added ones):

```yaml
- name: potential_gpa_credits_cum_projected
  data_type: float64
  description: >-
    Sum of potential GPA credit hours across all years, including in-progress
    current-year courses — the denominator behind `cumulative_y1_gpa_projected`.
- name: potential_gpa_credits_current_year
  data_type: float64
  description: >-
    Potential GPA credit hours the student is enrolled in for the current
    academic year. NULL when the student has no current-year GPA credits.
- name: gpa_needed_for_cumulative_3_0
  data_type: float64
  description: >-
    Weighted Y1 GPA the student must average across all current-year GPA credits
    to finish with a projected cumulative Y1 GPA of exactly 3.00. Negative
    values mean 3.00 is already guaranteed; values above the student's scale
    maximum are not attainable this year. NULL when the student has no
    current-year GPA credits.
- name: is_cumulative_3_0_attainable
  data_type: boolean
  description: >-
    True when `gpa_needed_for_cumulative_3_0` is at or below the credit-weighted
    maximum weighted GPA achievable across the student's current-year courses.
    NULL when the needed value is NULL.
```

(The union model selects `ur.*`, so the columns flow through automatically — the
YAML addition documents them and keeps the column list authoritative. Note: the
kipptaf model's own new-column ordering places union-sourced columns before the
two kipptaf-computed band columns in the relation; YAML order is documentation
only and does not need to match.)

- [ ] **Step 6: Smoke-compile against dev, then seed staging and get CI-ready**

Dev compile (dev sources resolve to the `zz_anthonygwalters_*` datasets built in
Tasks 1-4):

```bash
uv run dbt compile \
  --select int_powerschool__gpa_cumulative_year int_powerschool__gpa_cumulative \
  --project-dir src/dbt/kipptaf --target dev
```

Expected: compiles; the union model's compiled SQL lists all nine district
columns plus `_dbt_source_relation`.

Then seed the staging (`zz_stg_*`) copies dbt Cloud CI reads. **These commands
recreate shared `zz_stg_*` tables — get the user's explicit go-ahead in the
immediately-preceding turn, or hand the commands to the user.** Run serially:

```bash
uv run dbt clone \
  --select int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year \
  --target staging --state target/prod --full-refresh \
  --project-dir src/dbt/kippnewark
uv run dbt clone \
  --select int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year \
  --target staging --state target/prod --full-refresh \
  --project-dir src/dbt/kippcamden
uv run dbt clone \
  --select int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year \
  --target staging --state target/prod --full-refresh \
  --project-dir src/dbt/kippmiami
```

Expected: each clone copies the two prod tables (rebuilt in Task 6) into
`zz_stg_<district>_powerschool`. This refreshes the stale
`int_powerschool__gpa_cumulative` staging copy (new columns) and creates the
year model's staging copy — without this, kipptaf CI fails with table-not-found
/ column-not-found.

- [ ] **Step 7: Lint, commit, push, open PR 2**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative_year.yml \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml
git -C /workspaces/teamster add \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative_year.yml \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_cumulative.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml
git -C /workspaces/teamster commit \
  -m "feat(kipptaf): union int_powerschool__gpa_cumulative_year and expose needed-GPA columns" \
  -m "Closes #4295" \
  -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git -C /workspaces/teamster push origin anthonygwalters/feat/claude-gpa-year-kipptaf
```

Open PR 2 via `mcp__github__create_pull_request` using the repo PR template
body, `Closes #4295` in the summary, base `main`. Not a draft.

Expected CI behavior: editing three `sources-kipp*.yml` files marks those
sources modified, so `state:modified+` fans out to every kipptaf model reading
them — a large CI build is expected and normal. If CI fails on a stale staging
relation for an unmodified upstream, follow the kipptaf CLAUDE.md staging-defer
recovery (broad `Clone - Staging` job, then a fresh build via empty-commit push,
not `dbt retry`).

---

## Task 8: PR 2 CI verification and merge handoff

**Files:** none.

- [ ] **Step 1: Watch both CI surfaces**

dbt Cloud is a commit status; Trunk/CodeQL/claude are check runs — check both:
`mcp__github__pull_request_read` with `get_status` AND `get_check_runs` on PR 2.
Wait for dbt Cloud terminal state before pushing any fix (a push cancels and
restarts the run).

- [ ] **Step 2: After dbt Cloud CI passes, review warnings**

Fetch `mcp__dbt__get_job_run_error` with `run_id` of the CI run and
`warning_only: true`. Warnings unchanged from `main` are pre-existing — search
for an existing tracker before filing anything new. Confirm the kipptaf
uniqueness test on the new union model passed.

- [ ] **Step 3: Final verification queries against the PR schema (optional but
      cheap)**

Sanity-check the union row counts by district via BigQuery MCP against the
per-PR schema (`dbt_cloud_pr_<job_definition_id>_<pr_num>_<schema>` — read the
job definition id from the CI run's profile-creation step name):

```sql
select _dbt_source_project, count(*) as n_rows, countif(is_projected) as n_projected,
from `teamster-332318.dbt_cloud_pr_<job_definition_id>_<pr_num>_kipptaf_powerschool.int_powerschool__gpa_cumulative_year`
group by _dbt_source_project
```

Expected: three districts present; `n_projected` roughly equals each district's
currently-enrolled MS/HS student count with any GPA history. (This query has two
placeholders that are only knowable at CI time — job definition id and PR number
— substitute both before running.)

- [ ] **Step 4: Hand off for merge**

User reviews and squash-merges PR 2, which closes #4295. Post-merge, Dagster's
kipptaf deploy materializes the new union table. Downstream surfacing (`rpt_*` /
marts / Cube) is explicitly out of scope — a follow-up effort.

---

## Plan Self-Review (completed at authoring time)

- **Spec coverage:** Part 1 (four columns + formula + attainability + edge
  behavior) → Task 1. Part 2 (year model, two row sources, grade level, Paterson
  guard) → Task 2. Testing section (uniqueness, two unit tests, reconciliation
  singular test) → Tasks 1-3. Validation section (prod-data projected-row
  reconciliation per district, stored-row reconciliation, row counts) → Tasks
  3-5. kipptaf layer + deployment sequencing (two PRs, staging seeding) → Tasks
  6-8. Non-goals respected: no rpt/mart surfacing, no unweighted needed-GPA, no
  bands/snapshot on the year model, no Paterson rows.
- **Placeholder scan:** the only unresolved values are PR-2 CI-time identifiers
  (job definition id, PR number) in Task 8 Step 3, which cannot exist until CI
  runs and are called out explicitly at the query.
- **Type consistency:** column names/types match across Task 1 (producer), Task
  2 (consumer of the projected columns), Task 3 (test reads), and Task 7
  (kipptaf YAML) — `potential_gpa_credits_cum_projected`,
  `gpa_needed_for_cumulative_3_0`, `is_cumulative_3_0_attainable`,
  `potential_gpa_credits_current_year`, and the nine year-model columns.
