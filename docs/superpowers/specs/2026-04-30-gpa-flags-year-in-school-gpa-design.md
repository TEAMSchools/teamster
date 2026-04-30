# GPA Flags Report: year_in_school_gpa Design

## Problem

`rpt_gsheets__gpa_flags_report` identifies students who have a null cumulative
GPA when one is expected. The eligibility guard for this flag is:

```sql
and year_in_school > 1
```

`year_in_school` is derived from enrollment history — it increments any time a
student has a prior enrollment record at the same school, regardless of how
brief that enrollment was. A student enrolled for a single day in a prior year
will show `year_in_school = 2` in the current year.

However, a cumulative GPA only exists if a student has completed at least one
full year of grading at the school — specifically, if Y1 stored grades exist in
PowerSchool. A student who was enrolled briefly last year and never completed
enough of the year to earn stored grades will have `year_in_school = 2` but a
null `cumulative_y1_gpa`, triggering a false positive on the flag.

This was confirmed against current production data: 6 of the 8 students
currently on the report are flagged for null GPA. Whether each is a false
positive depends on the individual student's enrollment history; this fix
resolves the root cause automatically by tying the eligibility check to actual
completed grading rather than enrollment count.

## Proposed Solution

Add a new field `year_in_school_gpa` to `int_powerschool__gpa_cumulative` that
counts the number of distinct academic years in which a student has at least one
Y1 stored grade at their current school. Replace `year_in_school > 1` in the
report's null GPA filter with `year_in_school_gpa >= 1`.

This aligns the eligibility condition directly with the precondition for
cumulative GPA to exist: a completed school year with stored grades.

## Data Model

### `int_powerschool__gpa_cumulative` (powerschool project)

The model already rolls up Y1 stored grades from `stg_powerschool__storedgrades`
(filtered to `storecode = 'Y1'`) in the `grades_union` CTE. In-progress
projected grades from `base_powerschool__final_grades` have
`potentialcrhrs = null` by design, making `potentialcrhrs is not null` a
reliable signal for completed Y1 grade rows only.

New field added to the `points_rollup` CTE and final SELECT:

```sql
count(
    distinct if(potentialcrhrs is not null, academic_year, null)
) as year_in_school_gpa
```

- Type: `INT64`
- Value: 0 if no completed years at this school; 1+ if the student has prior Y1
  stored grades

### `rpt_gsheets__gpa_flags_report` (kipptaf project)

The `gpa_with_enrollment` CTE gains `g.year_in_school_gpa`. The null GPA branch
of the UNION ALL changes:

```sql
-- before
and year_in_school > 1

-- after
and year_in_school_gpa >= 1
```

No change to the output columns of the report — `year_in_school_gpa` is used
only as a filter condition.

## What Does Not Change

- `year_in_school` is unchanged — it remains a pass-through enrollment metric
  used in the report output for display purposes
- The unweighted-exceeds-weighted flag is unchanged
- The date window condition (`between Oct 15 and Jun 15`) is unchanged
- The `grade_level >= 9` and `schoolid != 999999` guards are unchanged

## Success Criteria

1. `int_powerschool__gpa_cumulative` gains a `year_in_school_gpa` INT64 column
   declared in its properties YAML
2. A dbt unit test verifies the count logic for three cases: two completed
   years, one completed year, and zero completed years (non-Y1 storecode only)
3. Students currently flagged as false positives (brief prior-year enrollment,
   no completed grading) no longer appear on the null GPA flag
4. Students with a genuine prior completed year and a missing GPA still appear

## Affected Files

| File                                                                                         | Change                                            |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`            | Add field to `points_rollup` CTE and final SELECT |
| `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml` | Add column declaration                            |
| `src/dbt/powerschool/models/sis/intermediate/unit_tests/int_powerschool__gpa_cumulative.yml` | New unit test                                     |
| `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gpa_flags_report.sql`            | Pull `year_in_school_gpa` from CTE; update filter |
| `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__gpa_flags_report.yml` | Update description                                |

## GitHub Issue

[TEAMSchools/teamster#3771](https://github.com/TEAMSchools/teamster/issues/3771)
