# GPA Flags: year_in_school_gpa Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blunt `year_in_school > 1` guard in
`rpt_gsheets__gpa_flags_report` with a new `year_in_school_gpa` field that
counts only completed academic years with Y1 stored grades, eliminating false
positives caused by brief prior-year enrollment.

**Architecture:** Add `year_in_school_gpa` (INT64) to
`int_powerschool__gpa_cumulative` by counting distinct academic years where
`potentialcrhrs IS NOT NULL` (i.e. Y1 stored grades exist) in the
`points_rollup` CTE. The report's null GPA filter swaps `year_in_school > 1` for
`year_in_school_gpa >= 1`.

**Tech Stack:** dbt (BigQuery dialect), PowerSchool source data, kipptaf network
analytics project.

---

## File Map

| File                                                                                         | Change                                                                                                               |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`            | Add `year_in_school_gpa` to `points_rollup` CTE and final SELECT                                                     |
| `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml` | Add `year_in_school_gpa` column (int64, with description)                                                            |
| `src/dbt/powerschool/models/sis/intermediate/unit_tests/int_powerschool__gpa_cumulative.yml` | New: dbt unit test verifying the count logic                                                                         |
| `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gpa_flags_report.sql`            | Add `g.year_in_school_gpa` to `gpa_with_enrollment` CTE; replace `year_in_school > 1` with `year_in_school_gpa >= 1` |
| `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__gpa_flags_report.yml` | Update description to reflect new filter logic                                                                       |

---

## Task 1: Add `year_in_school_gpa` to `int_powerschool__gpa_cumulative`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`

- [ ] **Step 1: Add the aggregation to `points_rollup`**

In `int_powerschool__gpa_cumulative.sql`, the `points_rollup` CTE currently
groups by `studentid, schoolid` and sums credit/point columns from
`with_weighted_points`. Add a count of distinct completed academic years:

```sql
    points_rollup as (
        select
            studentid,
            schoolid,

            sum(weighted_points) as weighted_points,
            sum(weighted_points_core) as weighted_points_core,
            sum(weighted_points_projected) as weighted_points_projected,
            sum(weighted_points_projected_s1) as weighted_points_projected_s1,
            sum(
                weighted_points_projected_s1_unweighted
            ) as weighted_points_projected_s1_unweighted,
            sum(
                weighted_points_projected_unweighted
            ) as weighted_points_projected_unweighted,
            sum(unweighted_points) as unweighted_points,
            sum(earnedcrhrs) as earned_credits_cum,
            sum(earnedcrhrs_projected) as earned_credits_cum_projected,
            sum(earnedcrhrs_projected_s1) as earned_credits_cum_projected_s1,
            sum(potentialcrhrs) as potentialcrhrs,
            sum(potentialcrhrs_core) as potentialcrhrs_core,
            sum(potentialcrhrs_projected) as potentialcrhrs_projected,
            sum(potentialcrhrs_projected_s1) as potentialcrhrs_projected_s1,

            sum(
                if(
                    academic_year < {{ var("current_academic_year") }},
                    earnedcrhrs,
                    potentialcrhrs
                )
            ) as potential_credits_cum,

            count(
                distinct if(potentialcrhrs is not null, academic_year, null)
            ) as year_in_school_gpa,
        from with_weighted_points
        group by studentid, schoolid
    )
```

- [ ] **Step 2: Add the field to the final SELECT**

In the final `select` of `int_powerschool__gpa_cumulative.sql`, append
`year_in_school_gpa` after `core_cumulative_y1_gpa`:

```sql
select
    studentid,
    schoolid,
    earned_credits_cum,
    potential_credits_cum,
    earned_credits_cum_projected,
    earned_credits_cum_projected_s1,

    round(safe_divide(weighted_points, potentialcrhrs), 2) as cumulative_y1_gpa,
    round(
        safe_divide(unweighted_points, potentialcrhrs), 2
    ) as cumulative_y1_gpa_unweighted,
    round(
        safe_divide(weighted_points_projected, potentialcrhrs_projected), 2
    ) as cumulative_y1_gpa_projected,
    round(
        safe_divide(weighted_points_projected_s1, potentialcrhrs_projected_s1), 2
    ) as cumulative_y1_gpa_projected_s1,
    round(
        safe_divide(
            weighted_points_projected_s1_unweighted, potentialcrhrs_projected_s1
        ),
        2
    ) as cumulative_y1_gpa_projected_s1_unweighted,
    round(
        safe_divide(weighted_points_projected_unweighted, potentialcrhrs_projected), 2
    ) as cumulative_y1_gpa_projected_unweighted,
    round(
        safe_divide(weighted_points_core, potentialcrhrs_core), 2
    ) as core_cumulative_y1_gpa,
    year_in_school_gpa,
from points_rollup
```

---

## Task 2: Update `int_powerschool__gpa_cumulative` properties YAML

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`

- [ ] **Step 1: Add the new column entry**

Append `year_in_school_gpa` to the `columns` list. Because this column has a
data test (`not_null` is not required here, but it should be documented), add it
with a description:

```yaml
models:
  - name: int_powerschool__gpa_cumulative
    columns:
      - name: studentid
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: earned_credits_cum
        data_type: float64
      - name: potential_credits_cum
        data_type: float64
      - name: earned_credits_cum_projected
        data_type: float64
      - name: earned_credits_cum_projected_s1
        data_type: float64
      - name: cumulative_y1_gpa
        data_type: float64
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
      - name: cumulative_y1_gpa_projected
        data_type: float64
      - name: cumulative_y1_gpa_projected_s1
        data_type: float64
      - name: cumulative_y1_gpa_projected_s1_unweighted
        data_type: float64
      - name: cumulative_y1_gpa_projected_unweighted
        data_type: float64
      - name: core_cumulative_y1_gpa
        data_type: float64
      - name: year_in_school_gpa
        description: >
          Count of distinct academic years in which the student has at least one
          Y1 stored grade at this school. Used to determine whether a null
          cumulative GPA represents a data quality issue (student completed a
          prior year but has no GPA) versus expected absence of data (student
          has no completed school years at this school).
        data_type: int64
```

Note: `cumulative_y1_gpa_projected_unweighted` was present in the SQL but
missing from the original YAML — add it here while the file is open (it's a
contract-enforced model so the column must be declared).

---

## Task 3: Write the dbt unit test

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/unit_tests/int_powerschool__gpa_cumulative.yml`

The test verifies three cases:

- A student with two Y1 stored grades across two academic years →
  `year_in_school_gpa = 2`
- A student with one Y1 stored grade → `year_in_school_gpa = 1`
- A student with only non-Y1 stored grades → `year_in_school_gpa = 0`

- [ ] **Step 1: Create the unit test file**

```yaml
unit_tests:
  - name: test_year_in_school_gpa_counts_completed_years
    model: int_powerschool__gpa_cumulative
    given:
      - input: ref('stg_powerschool__storedgrades')
        rows:
          # student 1: two completed Y1 years → year_in_school_gpa = 2
          - studentid: 1
            schoolid: 100
            course_number: "ENG101"
            academic_year: 2023
            storecode: "Y1"
            excludefromgpa: 0
            excludefromgraduation: 0
            potentialcrhrs: 1.0
            earnedcrhrs: 1.0
            gpa_points: 3.0
            gradescale_name_unweighted: "standard"
            percent: 85.0
            credit_type: "ENG"
          - studentid: 1
            schoolid: 100
            course_number: "MATH101"
            academic_year: 2024
            storecode: "Y1"
            excludefromgpa: 0
            excludefromgraduation: 0
            potentialcrhrs: 1.0
            earnedcrhrs: 1.0
            gpa_points: 3.0
            gradescale_name_unweighted: "standard"
            percent: 85.0
            credit_type: "MATH"
          # student 2: one completed Y1 year → year_in_school_gpa = 1
          - studentid: 2
            schoolid: 100
            course_number: "ENG101"
            academic_year: 2024
            storecode: "Y1"
            excludefromgpa: 0
            excludefromgraduation: 0
            potentialcrhrs: 1.0
            earnedcrhrs: 1.0
            gpa_points: 2.0
            gradescale_name_unweighted: "standard"
            percent: 75.0
            credit_type: "ENG"
          # student 3: only Q1 storecode (not Y1) → year_in_school_gpa = 0
          - studentid: 3
            schoolid: 100
            course_number: "ENG101"
            academic_year: 2024
            storecode: "Q1"
            excludefromgpa: 0
            excludefromgraduation: 0
            potentialcrhrs: 1.0
            earnedcrhrs: 1.0
            gpa_points: 3.0
            gradescale_name_unweighted: "standard"
            percent: 85.0
            credit_type: "ENG"
      - input: ref('int_powerschool__gradescaleitem_lookup')
        rows:
          - gradescale_name: "standard"
            min_cutoffpercentage: 70.0
            max_cutoffpercentage: 100.0
            grade_points: 3.0
      - input: ref('base_powerschool__final_grades')
        rows: []
      - input: ref('base_powerschool__student_enrollments')
        rows: []
    expect:
      rows:
        - studentid: 1
          schoolid: 100
          year_in_school_gpa: 2
        - studentid: 2
          schoolid: 100
          year_in_school_gpa: 1
        - studentid: 3
          schoolid: 100
          year_in_school_gpa: 0
```

- [ ] **Step 2: Run the unit test to verify it fails before implementation**

```bash
cd src/dbt/powerschool
uv run dbt test --select int_powerschool__gpa_cumulative --indirect-selection=cautious
```

Expected: error or failure — `year_in_school_gpa` does not exist yet in the
model.

- [ ] **Step 3: Run the unit test after Task 1 is complete to verify it passes**

```bash
cd src/dbt/powerschool
uv run dbt test --select int_powerschool__gpa_cumulative --indirect-selection=cautious
```

Expected: PASS for `test_year_in_school_gpa_counts_completed_years`.

---

## Task 4: Compile and spot-check `int_powerschool__gpa_cumulative`

**Files:** none (verification only)

- [ ] **Step 1: Compile the model to catch SQL errors**

```bash
cd src/dbt/kipptaf
uv run dbt compile --select int_powerschool__gpa_cumulative
```

Expected: no compilation errors.

- [ ] **Step 2: Spot-check production data via BigQuery MCP**

Run this query to confirm the field is populated and non-negative for a sample
of students:

```sql
SELECT
    studentid,
    schoolid,
    cumulative_y1_gpa,
    year_in_school_gpa
FROM `teamster-332318.kippcamden_powerschool.int_powerschool__gpa_cumulative`
ORDER BY year_in_school_gpa DESC
LIMIT 20
```

Expected: `year_in_school_gpa` is 0 or a positive integer; students with a
non-null `cumulative_y1_gpa` have `year_in_school_gpa >= 1`.

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -F .claude/scratch/commit-msg.txt
```

Commit message to write to `.claude/scratch/commit-msg.txt`:

```text
feat(powerschool): add year_in_school_gpa to int_powerschool__gpa_cumulative

Counts distinct academic years with Y1 stored grades per student/school.
Resolves false positives in the GPA flags report caused by brief prior-year
enrollment that increments year_in_school without generating a cumulative GPA.

Closes #3771
```

---

## Task 5: Update `rpt_gsheets__gpa_flags_report`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gpa_flags_report.sql`

- [ ] **Step 1: Add `year_in_school_gpa` to the `gpa_with_enrollment` CTE and
      fix the filter**

Replace the entire file with:

```sql
with
    gpa_with_enrollment as (
        select
            g.studentid,
            g.schoolid,
            g.cumulative_y1_gpa,
            g.cumulative_y1_gpa_unweighted,
            g.year_in_school_gpa,

            e.academic_year,
            e.region,
            e.school_name,
            e.student_number,
            e.lastfirst,
            e.grade_level,
            e.year_in_school,
        from {{ ref("int_powerschool__gpa_cumulative") }} as g
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as e
            on g.studentid = e.studentid
            and g.schoolid = e.schoolid
            and {{ union_dataset_join_clause(left_alias="g", right_alias="e") }}
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.enroll_status = 0
            and e.rn_year = 1
    )

select
    academic_year,
    region,
    school_name,
    student_number,
    lastfirst as student_name,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    grade_level,
    year_in_school,
    'unweighted exceeds weighted' as test_failure_reason,
from gpa_with_enrollment
where cumulative_y1_gpa_unweighted > cumulative_y1_gpa

union all

select
    academic_year,
    region,
    school_name,
    student_number,
    lastfirst as student_name,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    grade_level,
    year_in_school,
    'cumulative gpa is null' as test_failure_reason,
from gpa_with_enrollment
where
    cumulative_y1_gpa is null
    and schoolid != 999999
    and grade_level >= 9
    and year_in_school_gpa >= 1
    and current_date(
        '{{ var("local_timezone") }}'
    ) between date({{ var("current_academic_year") }}, 10, 15) and date(
        {{ var("current_academic_year") + 1 }}, 06, 15
    )
```

---

## Task 6: Update `rpt_gsheets__gpa_flags_report` properties YAML

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__gpa_flags_report.yml`

- [ ] **Step 1: Update the model description and replace `year_in_school` column
      note**

The current description references `year in school` as the eligibility
criterion. Update it to reflect the new field:

```yaml
models:
  - name: rpt_gsheets__gpa_flags_report
    description: >
      Surfaces potential cumulative GPA data quality issues for currently
      enrolled students to support review by the academics and operations teams.
      Each row represents a student flagged for one of two conditions: their
      unweighted cumulative GPA exceeds their weighted GPA, or their cumulative
      GPA is null despite meeting eligibility criteria defined by grade level,
      completed GPA years at the school, and academic calendar thresholds. The
      null GPA flag uses year_in_school_gpa (from
      int_powerschool__gpa_cumulative) rather than year_in_school to avoid false
      positives from students with brief prior-year enrollment who never
      completed a full year of grading. Flags are only surfaced during defined
      windows of the school year, aligned to the grading calendar for each
      region. This report is also the source of truth for the corresponding dbt
      data quality test, which alerts the data team via Slack when
      weighted/unweighted inversions are detected.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - test_failure_reason
          config:
            store_failures: true
    columns:
      - name: academic_year
        data_type: int64
      - name: region
        data_type: string
      - name: school_name
        data_type: string
      - name: student_number
        data_type: int64
      - name: student_name
        data_type: string
      - name: cumulative_y1_gpa
        data_type: float64
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
      - name: grade_level
        data_type: int64
      - name: year_in_school
        data_type: int64
      - name: test_failure_reason
        data_type: string
```

---

## Task 7: Verify the full report in kipptaf and commit

**Files:** none (verification only)

- [ ] **Step 1: Compile the report**

```bash
cd src/dbt/kipptaf
uv run dbt compile --select rpt_gsheets__gpa_flags_report
```

Expected: no compilation errors.

- [ ] **Step 2: Preview the report output**

```bash
cd src/dbt/kipptaf
uv run dbt show --select rpt_gsheets__gpa_flags_report --limit 50
```

Expected: previously-flagged false-positive students (those with
`year_in_school = 2` but no prior-year GPA) no longer appear in the
`cumulative gpa is null` results. Students with a genuine prior completed year
and a null GPA should still appear.

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -F .claude/scratch/commit-msg.txt
```

Commit message to write to `.claude/scratch/commit-msg.txt`:

```text
fix(kipptaf): use year_in_school_gpa in GPA flags report null check

Replaces year_in_school > 1 with year_in_school_gpa >= 1 in the null
cumulative GPA flag. Eliminates false positives for students enrolled
briefly in a prior year who never completed enough grading to generate
a Y1 stored grade.

Closes #3771
```
