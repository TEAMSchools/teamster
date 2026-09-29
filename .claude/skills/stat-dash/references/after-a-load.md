## Procedure: A roster column is only part-colored

The teacher/student roster view draws one colored bar per student per
discipline, and the bar must span the full width of its column. When part of the
column is blank, Tableau is drawing two marks in that cell. The view is fine;
the data has two rows where it should have one.

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

With a hit, pull the underlying rows and compare `test_status`:

```sql
select student_test_uuid, test_status, test_date, test_scale_score,
from `teamster-332318`.kipptaf_cambium.stg_cambium__njsla
where state_student_identifier = <the state id from the flagged row>
```

A `pending` row beside a `completed` one is the known Cambium case, filtered in
`int_pearson__all_assessments` as of this writing. Anything else is new: write
down what actually distinguishes the two rows before changing any model.

### Catch it at load time instead of in the workbook

Run the first query after every Cambium load, before anyone opens the dashboard.
The grain uniqueness test on `int_pearson__all_assessments` asserts the same
thing, so a dbt failure on that model's `unique_combination_of_columns` is this
defect arriving through the front door -- read the failing rows rather than
re-running the build.

---
