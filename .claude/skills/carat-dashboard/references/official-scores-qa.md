# Official scores — QA after a crosswalk update

Run this when the `collegeboard-id-crosswalk` skill hands off, after the user
has pasted new College Board ID mappings and the crosswalk staging model
reconciles. It ends in a three-part report (step 5): what changed and when it
reached prod, a draft for KIPP Forward, and a preview of how the new scores
moved the tracked metrics.

Record the paste time first; every step compares against it.

## The chain

| Step | AP                                     | PSAT                                                                                   | SAT                                                        | Kind  |
| ---- | -------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ----- |
| 1    | `int_collegeboard__ap_unpivot`         | `int_collegeboard__psat_unpivot`                                                       | `int_collegeboard__sat_unpivot`                            | table |
| 2    | `int_assessments__ap_assessments`      | `int_assessments__college_assessment`                                                  | —                                                          | view  |
| 3    | —                                      | `int_assessments__all_college_assessments`                                             | —                                                          | table |
| 4    | `rpt_tableau__ap_assessment_dashboard` | `rpt_tableau__college_assessment_dashboard_*`, `rpt_gsheets__college_assessments_wide` | `rpt_gsheets__kippfwd_sfsat`, `rpt_gsheets__kippfwd_ogsat` | views |

Official SAT on the dashboard comes from kippadb, not College Board files, so a
SAT crosswalk paste changes only the KIPP Forward SAT sheets in the Unified KFWD
Processes Document. They list the SAT scores Salesforce doesn't have yet. For a
SAT-only load, run step 1 on `int_collegeboard__sat_unpivot`, confirm the new
scores now appear on those sheets, and skip steps 2 to 4. In the report, say the
scores reach the dashboard only after they're loaded into Salesforce.

Views read live, so a score is in prod once the last table above it has rebuilt:
step 1 for AP and SAT, step 3 for PSAT. Tableau shows it after the workbook's
next extract refresh.

## 1. When it reached prod

For each table in the chain, call `mcp__dagster__get_asset_materializations`
(asset key `kipptaf/<dataset>/<model>`, for example
`kipptaf/collegeboard/int_collegeboard__psat_unpivot`) and report the first
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

## 3. Performance preview

Show how the load moved the metrics the `_current` view tracks, network-wide and
by school:

```bash
uv run dbt compile --select rpt_tableau__college_assessment_dashboard_current \
    --project-dir src/dbt/kipptaf --target prod
uv run python .claude/skills/carat-dashboard/scripts/current_metrics_before_after.py \
    "<paste time> America/New_York" [--by-school]
```

It runs the view's own SQL twice, once with the scores table read as of the
paste, and prints each metric's percent met before and now, the change, and the
goal. Goals, thresholds and the roster are read as of now in both runs, so any
change comes from the load. The attempts metrics (`*_1_attempt`,
`*_2_plus_attempts`) are the share of students in the group meeting the expected
test count; the ready metrics are the share at HS Grad-Ready or College-Ready.

AP has no `_current` metrics, so an AP-only load skips this step. Report only
the tests the load touched, lead with the attempts metrics, and put each metric
beside its goal. A metric with no goal (`None`) is tracked but not targeted; say
so rather than printing an empty goal.

## 4. Scores added, by school and grade

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

## 5. Hand over the report

Three parts, in this order.

1. **Report to the user** (terminal): the crosswalk tab and link, rows pasted,
   the staging row-count check; the step 1 table of rebuild times with the line
   that views read live and Tableau shows the scores after its next refresh; the
   step 2 before/now table with whether the student increase matches the rows
   pasted; anything still open (`flagged_for_review`, `ambiguous`, `no_match`).
2. **Draft for KIPP Forward**, opened with a one-line "Written for" note: a
   short email naming the tests and administrations, the step 4 table with its
   total, how many students are still being matched, and that it is internal to
   the network. No student names or ids. Flag every cell under 10 to the user
   before they send it, and say whether the total lets someone recover it.
3. **Performance preview**: the step 3 tables, attempts first, then readiness,
   each metric beside its goal, plus one by-school line for the headline metric.
   The KIPP Forward draft carries a short version: the attempts lines and one
   readiness line per test.
