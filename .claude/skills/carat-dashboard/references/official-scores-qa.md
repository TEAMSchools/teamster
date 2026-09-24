# Official scores — QA after a crosswalk update

Run this when the `collegeboard-id-crosswalk` skill hands off, after the user
has pasted new College Board ID mappings and the crosswalk staging model
reconciles. It produces three things for the user: what changed, when it reached
prod, and a summary to share with KIPP Forward.

Record the paste time first; every step compares against it.

## The chain

| Step | AP                                     | SAT, PSAT                                                                                                                                          | Kind  |
| ---- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| 1    | `int_collegeboard__ap_unpivot`         | `int_collegeboard__sat_unpivot`, `int_collegeboard__psat_unpivot`                                                                                  | table |
| 2    | `int_assessments__ap_assessments`      | `int_assessments__college_assessment`                                                                                                              | view  |
| 3    | —                                      | `int_assessments__all_college_assessments`                                                                                                         | table |
| 4    | `rpt_tableau__ap_assessment_dashboard` | `rpt_tableau__college_assessment_dashboard_*`, `rpt_gsheets__kippfwd_sfsat`, `rpt_gsheets__kippfwd_ogsat`, `rpt_gsheets__college_assessments_wide` | views |

Views read live, so a score is in prod once the last table above it has rebuilt:
step 1 for AP, step 3 for SAT and PSAT. Tableau shows it after the workbook's
next extract refresh.

## 1. When it reached prod

For each table in the chain, call `mcp__dagster__get_asset_materializations`
(asset key `kipptaf/<dataset>/<model>`, for example
`kipptaf/collegeboard/int_collegeboard__sat_unpivot`) and report the first
materialization after the paste time, converted to local time. A table with no
materialization after the paste has not rebuilt yet; say so rather than
reporting old data as new.

## 2. What changed

Count each table now and as of the paste, with BigQuery time travel. Run the two
halves as separate queries: BigQuery rejects one table referenced at two
different times in one query. Report counts, never names or ids.

```sql
select
    scope, count(*) as score_rows, count(distinct student_number) as students,
from
    `teamster-332318.kipptaf_assessments.int_assessments__all_college_assessments`
    for system_time as of timestamp('<paste time>')
where test_type = 'Official'
group by scope
```

Then the same query without the `for system_time` line. Time travel reaches back
7 days only, so run this within a week of the paste. For AP, compare
`int_collegeboard__ap_unpivot` the same way. The student increase should roughly
equal the rows pasted for that test; a shortfall means a pasted student's scores
did not flow, and a crosswalk row that maps to a student outside the enrollment
spine is the usual cause.

## 3. The KIPP Forward summary

The newly resolved students are the `student_number` values in the file the user
pasted. Aggregate their scores by test, administration, school, and grade:

```sql
with
    pasted as (
        select student_number,
        from unnest([<student numbers from the pasted file>]) as student_number
    )

select
    s.scope,
    s.academic_year,
    s.test_month,
    e.school,
    e.grade_level,
    count(distinct s.student_number) as students,
    countif(s.is_overall_score = 1) as total_scores,
from `teamster-332318.kipptaf_assessments.int_assessments__all_college_assessments` as s
inner join pasted as p on s.student_number = p.student_number
left join
    `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments` as e
    on s.student_number = e.student_number
    and s.academic_year = e.academic_year
    and e.rn_year = 1
where s.test_type = 'Official'
group by s.scope, s.academic_year, s.test_month, e.school, e.grade_level
```

For AP, aggregate `int_collegeboard__ap_unpivot` the same way. Never slice by a
demographic, and mark any cell under 10 students so the user can decide whether
to combine or drop it before sharing; the repo has no automated small-cell
suppression (#4237).

Hand it over as a short message written for KIPP Forward: which tests and
administrations, how many students and scores were added, when they reached the
data, and when the dashboard will show them (the next Tableau refresh). State
that it is internal to the network. No student names or ids.
