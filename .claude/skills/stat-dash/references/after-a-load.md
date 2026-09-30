# After a load: grain, duplicates and the detector

## Procedure: After every Cambium load

Run these before anyone opens the dashboard:

1. The detector, `test_incorrect_student_number_pearson`. New absent-id rows go
   through [crosswalk.md](crosswalk.md).
2. The duplicate query below. Two tests guard the same defect at build time:
   `unique_combination_of_columns` on `int_assessments__state_nj_scores`
   (`student_number`, `academic_year`, `aligned_test_code`,
   `administration_round`, resolved ids only) and on
   `rpt_tableau__state_assessments_dashboard` (`academic_year`,
   `student_number`, `test_code`, `admin`, `results_type`). A failure of either
   is a duplicate attempt arriving: read the failing rows rather than re-running
   the build. The first test runs after `int_assessments__state_nj_scores` is
   built, so the duplicates are already in that table when it fails. Check
   whether `int_assessments__state_scores` rebuilt after it: both `rpt_` models
   are views over that table, so if it rebuilt, the duplicates are in what
   Tableau reads. Only the extract, refreshed on Tableau Server, stands between
   them and viewers; fix before its next refresh.

## Procedure: A roster column is only part-colored

The Teacher/Student Roster view draws one colored bar per student per
discipline, and the bar must span the full width of its column. When part of the
column is blank, Tableau is drawing two marks in that cell: the data has two
rows where it should have one.

Do not hunt for it by selecting filters one at a time. Ask the warehouse:

```sql
select
    academic_year,
    region,
    school,
    test_code,
    season,
    `admin`,
    count(*) - count(distinct student_number) as excess_rows,
from `teamster-332318`.kipptaf_tableau.rpt_tableau__state_assessments_dashboard
group by academic_year, region, school, test_code, season, `admin`
having count(*) > count(distinct student_number)
```

`season` and `admin` must both be in the grouping. Leave them out and Miami
looks broken, because a Miami student legitimately has one row per FAST
administration window.

With a hit, pull the underlying Cambium rows and compare `test_status`
(`stg_cambium__eoc` and `stg_cambium__njgpa` have the same columns):

```sql
select student_test_uuid, test_status, test_date, test_scale_score,
from `teamster-332318`.kipptaf_cambium.stg_cambium__njsla
where state_student_identifier = <the state id from the flagged row>
```

A `pending` row beside a `completed` one is the known Cambium case: both Cambium
CTEs in the cambium package `int_cambium__all_assessments` keep only
`test_status = 'completed'`. Because that filter sits upstream of the detector,
a pending attempt never reaches the detector or the tiered matcher, so neither
will propose it for the sheet. Anything else is new: write down what
distinguishes the two rows before changing any model.
