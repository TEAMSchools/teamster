# Pass/fail courses in PowerSchool

Refs [#5092](https://github.com/TEAMSchools/teamster/issues/5092)

## Problem

Schools want pass/fail courses. A pass/fail course must print `P` or `F` on
report cards and transcripts, earn credit toward graduation, and stay out of
every GPA calculation.

The only PowerSchool setting that keeps a course out of GPA is
`courses.excludefromgpa`. PowerSchool itself computes the GPA, class rank, and
honor roll that print on report cards and transcripts, so that flag has to be
set. There is no alternative lever.

But the dbt models give that flag a second, unrelated job. Six models read
`exclude_from_gpa = 0` as a row-population filter meaning "this is a real
class." That works today only because the flag is set exclusively on
non-instructional containers.

A credit-bearing pass/fail course flagged `excludefromgpa = 1` therefore
inherits the "not a real class" treatment and vanishes from reporting it belongs
in.

### The coupling in one line

`base_powerschool__final_grades` derives a single column:

```sql
coalesce(sg_exclude_from_gpa, courses_excludefromgpa) as exclude_from_gpa
```

Everything downstream reads that one column for two different purposes: GPA
arithmetic, and "is this row a real course."

## Goals

A pass/fail course must:

1. Print `P` or `F` on report cards and transcripts.
1. Earn credit toward graduation, including mid-year, before grades store.
1. Contribute nothing to any GPA: term, semester, `Y1`, cumulative, projected,
   core, weighted, or unweighted.
1. Count as a failure when failed.
1. Appear on the DeansList transcript extract.
1. Appear on the high school early warning dashboard.

## Non-goals

- **Gradebook audit scope.** Pass/fail sections stay out of the gradebook audit.
  The existing `exclude_from_gpa = 0` filters in `rpt_tableau__gradebook_audit`
  and `int_extracts__gradebook_audit_student_flags` already achieve this and are
  left untouched.
- **Miami.** Miami runs on Focus, not PowerSchool. The Focus branch gets an
  explicit `false` and a comment.
- **Honor roll and class rank.** No dbt model reads `excludefromclassrank` or
  `excludefromhonorroll`. PowerSchool computes both natively.

## Evidence

Every number below was measured against the warehouse on 2026-08-31, not
assumed.

### The flag is currently synonymous with "not a real class"

Current-year rows in `kipptaf_powerschool.base_powerschool__final_grades`:

| Region   | Courses with `exclude_from_gpa = 1`    | Credit-bearing rows |
| -------- | -------------------------------------- | ------------------- |
| Newark   | Lunch, HR, Early Dismissal, Study Hall | 0                   |
| Camden   | Lunch, HR, Early Dismissal             | 0                   |
| Paterson | HR                                     | 0                   |

Zero credit-bearing rows in all 3 regions. That is why the proxy has held.

### A pass/fail grade scale already exists

`int_powerschool__gradescaleitem_lookup` shows a scale named `Pass Fail Scale`
in Newark and Camden, `gradescaleid` 346:

| Letter | `grade_points` | Cutoff range |
| ------ | -------------- | ------------ |
| `F`    | 0              | 0 to 59.9    |
| `P`    | 0              | 60 to 999.9  |

**Both letters carry `grade_points = 0`.** That is exactly why `excludefromgpa`
is load-bearing: without it, every `P` scores 0.0 grade points against real
credit hours and craters the GPA.

Paterson has no such scale and needs one created with the same name. Miami is
out of scope.

### Section-level grade scale overrides are unused today

`sections.gradescaleid` is staged but never read. Every dbt model resolves the
scale from `courses.gradescaleid`. Divergence in
`kipptaf_powerschool.base_powerschool__sections`:

| Region   | Current-year sections, `terms_yearid = 36` | Section scale differs from course |
| -------- | ------------------------------------------ | --------------------------------- |
| Newark   | 1824                                       | 0                                 |
| Camden   | 688                                        | 0                                 |
| Paterson | 140                                        | 0                                 |
| Miami    | 0 applicable                               | 0                                 |

`0` is PowerSchool's inherit-from-course sentinel and every current-year section
carries it. Divergence exists only historically: 1299 sections all-time, 27 of
them in Paterson in `terms_yearid = 35`, since cleaned up.

Four historical Newark sections carried scale 346 on a course with scale 874.
Section-level pass/fail is therefore not hypothetical, which is why the design
supports it.

### The unweighted CASE has a dead branch

`base_powerschool__sections.sql` contains:

```sql
case cou.gradescaleid
    when 991 then 976
    when 712 then 874
    /* MISSING GRADESCALE - default 2016+ */
    when null then 874
    else cou.gradescaleid
end
```

`case X when null` compares `X = NULL`, which is never true, so the branch is
dead. Verified: all 843 rows with a null course scale produce a null unweighted
scale, not `874`. All 843 are Focus rows from
`kippmiami_focus.int_focus__course_periods`, so the dead branch never mattered.
Dropping it is provably behavior-preserving.

### One model already behaves correctly and needs no change

`int_powerschool__final_grades_rollup` applies no exclusion filter at all. It
sums `potential_credit_hours` and counts `F` and `F*` across every final-grade
row. Non-instructional containers carry 0 credit hours and null letter grades,
so they contribute nothing.

That means the promotional-status path already handles pass/fail courses
correctly: `n_failing`, `n_failing_core`, `projected_credits_y1_term`, and the
25/50/85/120 credit gates in `int_reporting__promotional_status`. No change
needed there.

`int_students__athletic_eligibility` likewise counts `F` and `F*` from
`base_powerschool__final_grades` with no exclusion filter, so a failed pass/fail
course already affects eligibility. No change needed.

## PowerSchool configuration recipe

Per course, for a credit-bearing pass/fail course:

| Field                     | Value                           | Why                                                                      |
| ------------------------- | ------------------------------- | ------------------------------------------------------------------------ |
| `gradescaleid`            | a scale named `Pass Fail Scale` | Prints `P` or `F`, and is the fact dbt reads to identify pass/fail       |
| `excludefromgpa`          | `1`                             | The only lever PowerSchool honors. Both `P` and `F` carry 0 grade points |
| `excludefromclassrank`    | `1`                             | Class rank prints on transcripts                                         |
| `excludefromhonorroll`    | `1`                             | Same                                                                     |
| `credit_hours`            | greater than 0                  | Required for credit toward graduation                                    |
| `excludefromstoredgrades` | `0`                             | Grades must store to reach the transcript                                |
| `excludefromgraduation`   | `0` at store time               | Credits count toward graduation                                          |
| `credittype`              | the real subject                | See below                                                                |

**Do not invent a `PF` credit type.** `credittype` drives the core-GPA filter
`credit_type in ('MATH', 'SCI', 'ENG', 'SOC')` in
`int_powerschool__gpa_cumulative`, the `n_failing_core` calculation in
`int_powerschool__final_grades_rollup`, and graduation-requirement subject
mapping. A pass/fail English course keeps `credittype = 'ENG'`.

Paterson must create a scale named `Pass Fail Scale`. Keying on name rather than
id is deliberate: the regions are separate PowerSchool instances and ids do not
align across them.

## Commit 1: resolve the grade scale from the section

This commit must move no data. It exists so that pass/fail lands on a foundation
where the scale dbt reads matches the scale PowerSchool printed from.

### Why it is needed

If dbt only ever reads the course scale, section-level pass/fail is a silent
trap. Someone sets `Pass Fail Scale` on a section, PowerSchool prints `P`, and
dbt keeps computing A-to-F grade points off the course scale. The two disagree
with no error anywhere.

### Changes

In `base_powerschool__sections.sql`, add:

```sql
coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid) as gradescaleid_resolved,
```

Rename `courses_gradescaleid_unweighted` to `gradescaleid_unweighted_resolved`
and compute it over the resolved id, dropping the dead null branch:

```sql
case coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid)
    /* unweighted 2019+ */
    when 991
    then 976
    /* unweighted 2016-2018 */
    when 712
    then 874
    else coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid)
end as gradescaleid_unweighted_resolved,
```

The rename is deliberate rather than an added alias. The `courses_` prefix is
generated by `dbt_utils.star` for genuine passthroughs, and
`courses_gradescaleid_unweighted` is a hand-derived column borrowing that
prefix. Keeping both names would let a future reader pick the wrong one. The raw
`sections_gradescaleid` and `courses_gradescaleid` passthroughs are untouched.

### The 7 resolution sites to repoint

| File                                                                      | Line  | Current                              | Becomes                               |
| ------------------------------------------------------------------------- | ----- | ------------------------------------ | ------------------------------------- |
| `powerschool/models/sis/base/base_powerschool__sections.sql`              | 35-46 | the unweighted CASE                  | as above                              |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 118   | `et.courses_gradescaleid`            | `et.gradescaleid_resolved`            |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 127   | `et.courses_gradescaleid`            | `et.gradescaleid_resolved`            |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 343   | `y1.courses_gradescaleid`            | `y1.gradescaleid_resolved`            |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 348   | `y1.courses_gradescaleid_unweighted` | `y1.gradescaleid_unweighted_resolved` |
| `powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql` | 110   | `fg.courses_gradescaleid_unweighted` | `fg.gradescaleid_unweighted_resolved` |
| `kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`  | 1082  | `qg.courses_gradescaleid`            | `qg.gradescaleid_resolved`            |

`base_powerschool__course_enrollments` picks up the new columns automatically
through `dbt_utils.star`. `rpt_tableau__student_course_grades` also selects
`courses_gradescaleid` at lines 595, 628, and 664, which must follow.

### The rename sweep

Use `--include='*.{sql,yml,md}'`, per the repo rule that a model or column
rename must sweep markdown too. Specifically:

- 4 `properties/*.yml` files document the column:
  `base_powerschool__sections.yml` line 391,
  `base_powerschool__course_enrollments.yml` line 416,
  `base_powerschool__final_grades.yml` line 62, and the `kipptaf` copy at
  `kipptaf/models/powerschool/base/properties/base_powerschool__final_grades.yml`
  line 150.
- 6 unit-test fixture blocks in
  `powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`
  set `courses_gradescaleid_unweighted`, at lines 294, 309, 324, 339, 354,
  and 369.

### New test

Add a warn-severity singular test flagging any section whose resolved scale
differs from its course scale. A section override is legitimate, but it moves
GPA for those students, so it should surface in CI rather than silently.

## Commit 2: identify pass/fail and repoint 4 filters

### Where pass/fail is determined

Inline in `base_powerschool__sections.sql`, joined to the parent grade-scale
rows and keyed on name:

```sql
{# TODO: refactor to gsheet #}
coalesce(gs.name in ('Pass Fail Scale'), false) as is_pass_fail,
```

joined via:

```sql
left join
    {{ ref("stg_powerschool__gradescaleitem") }} as gs
    on coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid) = gs.id
    and gs.gradescaleid = -1
```

`gradescaleid = -1` selects parent scale rows rather than the individual letter
items, which is the same filter `int_powerschool__gradescaleitem_lookup` already
uses.

This sits beside the existing hardcoded unweighted CASE, which carries the same
`TODO: refactor to gsheet` marker, so it matches local precedent.

**Rejected alternatives.** A CSV seed: the repo contains no seeds at all,
despite `seed-paths` being configured in all 16 projects, so this would
establish a new convention for one row of data. A Google Sheets crosswalk: all
13 existing crosswalks live in `kipptaf`, and the GPA models that need this
column live in the `powerschool` package, which cannot reference `kipptaf`. A
PowerSchool course custom field: needs page customization, a new source table, a
staging model with a contract, 4 district configs, and per-course data entry
that can contradict the grade scale, giving 2 sources of truth.

### New columns

`base_powerschool__sections` gains `is_pass_fail`, flowing into
`base_powerschool__course_enrollments` through `dbt_utils.star`.

`base_powerschool__final_grades` passes `is_pass_fail` through and adds:

```sql
(exclude_from_gpa = 0 or is_pass_fail) as is_graded_course,
```

One definition, 4 readers. `is_graded_course` means "carries a real grade," as
against Lunch, HR, Early Dismissal, and Study Hall.

### Repoint 1: failure counts

`int_powerschool__gpa_term.sql` line 112 computes:

```sql
sum(if(y1_letter_grade like 'F%', 1, 0)) as n_failing_y1,
```

inside `grade_rollup`, which reads `grade_detail`. `grade_detail` filters
`where exclude_from_gpa = 0 and potential_credit_hours > 0`, so pass/fail rows
never arrive.

**Do not widen that filter.** Widening it pulls pass/fail rows into
`total_credit_hours_term`, `total_credit_hours_y1`, `grade_avg_term`,
`grade_avg_y1`, and both GPA numerators, leaving 6 columns that would each need
nulling. One miss silently moves a GPA.

Instead add a separate `failing_detail` CTE over the wider population, covering
both the current-year and prior-year branches, at grain
`(studentid, schoolid, yearid, storecode)`. Left-join it into `grade_rollup` and
take `n_failing_y1` from there. `grade_detail` is untouched, so no GPA column
can move by construction.

Pass/fail percents stay out of `grade_avg_term` and `grade_avg_y1`. A pass/fail
course has a real underlying percent but its reported grade is `P`, so including
it would change a grade average that nobody asked to change.

### Repoint 2: projected credits

`int_powerschool__gpa_cumulative.sql` has a `grades_union` of 3 branches. The
current-year branch at line 229 and the semester-1 branch both filter
`where fg.exclude_from_gpa = 0`, and the current-year branch is also where
`earnedcrhrs_projected` comes from.

This is a defect that predates pass/fail. Prior-year credits key on
`excludefromgraduation`, but current-year projected credits key on GPA
exclusion. Any course excluded from GPA loses its credits from projections all
year, then gains them back once grades store.

Add a **4th union branch** for current-year pass/fail rows contributing only
`earnedcrhrs_projected` and `earnedcrhrs_projected_s1`, with every GPA point and
potential-credit column null. Each existing branch already fills a subset of
columns and nulls the rest, so this matches the model's shape.

`potentialcrhrs_projected` must stay clean. It is both the GPA denominator in
`cumulative_y1_gpa_projected` and the input to `potentialcrhrs_current`, which
feeds `gpa_needed_for_cumulative_3_0` and the
`potentialcrhrs_current_max_known_unweighted` equality guard behind
`is_cumulative_3_0_attainable`. Pass/fail credits must never enter it.

### Repoints 3 and 4: extracts

| File                                                                          | Line | Current                       | Becomes                   |
| ----------------------------------------------------------------------------- | ---- | ----------------------------- | ------------------------- |
| `kipptaf/models/extracts/tableau/rpt_tableau__hs_early_warning_dashboard.sql` | 90   | `and gr.exclude_from_gpa = 0` | `and gr.is_graded_course` |
| `kipptaf/models/extracts/deanslist/rpt_deanslist__transcript_grades.sql`      | 57   | `and fg.exclude_from_gpa = 0` | `and fg.is_graded_course` |

### kipptaf propagation

`int_students__final_grades.sql` carries `is_pass_fail` on the PowerSchool
branch and hardcodes `false` on the Focus branch, with a comment recording that
Miami is out of scope.

`fct_grades_term.sql` adds `is_pass_fail` beside the existing
`is_excluded_from_gpa`. Without it, a mart consumer sees a course excluded from
GPA and cannot tell whether it is a pass/fail class or lunch. This is a contract
addition on a model exposed to Cube, so it needs a
`properties/fct_grades_term.yml` entry with `data_type: boolean` and a
description, following the `is_excluded_from_gpa` entry at line 184.

## Downstream inventory

Complete list of everything that reads the flag, so nothing is missed.

### Models that filter on it

| Model                                               | Purpose of the filter           | Action                          |
| --------------------------------------------------- | ------------------------------- | ------------------------------- |
| `int_powerschool__gpa_term`, main filter            | GPA arithmetic                  | unchanged                       |
| `int_powerschool__gpa_term`, `n_failing_y1`         | failure count                   | repoint 1                       |
| `int_powerschool__gpa_term`, prior-year branch      | GPA arithmetic                  | unchanged, covered by repoint 1 |
| `int_powerschool__gpa_cumulative`, point sums       | GPA arithmetic                  | unchanged                       |
| `int_powerschool__gpa_cumulative`, current-year, S1 | gates credits too               | repoint 2                       |
| `int_powerschool__gpa_cumulative_year`              | GPA arithmetic on stored grades | unchanged                       |
| `rpt_deanslist__transcript_gpas`                    | GPA arithmetic                  | unchanged                       |
| `rpt_deanslist__transcript_grades`                  | row population                  | repoint 4                       |
| `rpt_tableau__hs_early_warning_dashboard`           | row population                  | repoint 3                       |
| `rpt_tableau__gradebook_audit`                      | audit scope                     | unchanged, non-goal             |
| `int_extracts__gradebook_audit_student_flags`       | audit scope                     | unchanged, non-goal             |

### Models that carry it as a column without filtering

No change required, but each is a place a consumer could be relying on the old
meaning:

`fct_grades_term`, as `is_excluded_from_gpa`;
`rpt_tableau__gradebook_dashboard`; `rpt_tableau__student_course_grades`;
`rpt_tableau__gradebook_gpa`; `rpt_tableau__gradebook_es_comments`;
`rpt_tableau__gradebook_ms_hs_comments`; `rpt_tableau__gradebook_audit`;
`int_tableau__gradebook_audit_flags`;
`int_tableau__gradebook_audit_student_scaffold`;
`int_tableau__gradebook_audit_teacher_scaffold`;
`int_tableau__gradebook_audit_categories_teacher`;
`int_extracts__course_schedule_by_term`;
`int_extracts__course_enrollments_by_term`.

### Indirect consumers through the GPA models

`int_powerschool__gpa_term` feeds `fct_grades_gpa`,
`int_gpa__goal_student_metrics`, `int_powerschool__gpa_term_current`,
`int_powerschool__gpa_term_lookback`, `rpt_tableau__gpa_analysis`,
`rpt_tableau__gpa_cumulative_year`, `rpt_tableau__mtss_rti`,
`rpt_tableau__okrts_referrals`, `rpt_gsheets__gpa_roster`,
`rpt_gsheets__mtss_rti`, `rpt_gsheets__kippfwd_miami_roster`,
`rpt_deanslist__designations`, `rpt_deanslist__promo_status`, and
`rpt_deanslist__student_misc`.

`int_powerschool__gpa_cumulative` feeds `int_reporting__promotional_status`,
`int_extracts__student_enrollments`, `rpt_gsheets__gpa_flags_report`, and is
snapshotted in `kipptaf/snapshots/powerschool.yml`. A logic change writes new
snapshot history rather than restating old rows.

## Verification

Aggregate sums are not acceptable proof. Opposing student-level moves cancel to
zero. Every check below is a student-level diff against production.

### Commit 1 gate: exactly 0 differing rows

```sql
select count(*) as n_differing_rows
from {pr_schema}.int_powerschool__gpa_term as new
full outer join {prod_schema}.int_powerschool__gpa_term as old
    using (_dbt_source_relation, studentid, schoolid, yearid, term_name)
where
    new.studentid is null
    or old.studentid is null
    or abs(coalesce(new.gpa_term, -99) - coalesce(old.gpa_term, -99)) > 0.005
    or abs(coalesce(new.gpa_y1, -99) - coalesce(old.gpa_y1, -99)) > 0.005
    or abs(
        coalesce(new.gpa_y1_unweighted, -99)
        - coalesce(old.gpa_y1_unweighted, -99)
    )
    > 0.005
    or abs(coalesce(new.gpa_semester, -99) - coalesce(old.gpa_semester, -99))
    > 0.005
    or coalesce(new.n_failing_y1, -99) != coalesce(old.n_failing_y1, -99)
```

Run the same shape against `int_powerschool__gpa_cumulative` over
`cumulative_y1_gpa`, `cumulative_y1_gpa_unweighted`,
`cumulative_y1_gpa_projected`, `cumulative_y1_gpa_projected_unweighted`,
`cumulative_y1_gpa_projected_s1`, `cumulative_y1_gpa_projected_s1_unweighted`,
`core_cumulative_y1_gpa`, `earned_credits_cum`, `earned_credits_cum_projected`,
`earned_credits_cum_projected_s1`, `potential_credits_cum`,
`gpa_needed_for_cumulative_3_0`, and `is_cumulative_3_0_attainable`.

Both must return 0. Anything above 0 means the sentinel reading is wrong and the
commit stops.

### Commit 2 expected diff, stated before running

Exactly 3 columns may move, and only for students with a pass/fail enrollment:

| Column                            | Expected direction                    |
| --------------------------------- | ------------------------------------- |
| `n_failing_y1`                    | up, when a pass/fail course is failed |
| `earned_credits_cum_projected`    | up                                    |
| `earned_credits_cum_projected_s1` | up                                    |

Every GPA column must be unchanged: term, semester, `Y1`, `Y1` unweighted,
cumulative, projected cumulative, projected semester-1, core,
`gpa_needed_for_cumulative_3_0`, and `is_cumulative_3_0_attainable`. Any GPA
movement means the CTE or union-branch isolation leaked.

Because no pass/fail course is scheduled yet, the honest expectation on the
current warehouse is 0 differing rows in commit 2 as well. Prove the logic with
a dbt unit test that mocks a pass/fail enrollment rather than relying on
production data.

### Unit tests

Add unit tests, following the existing fixtures in
`int_powerschool__gpa_cumulative.yml`:

1. `int_powerschool__gpa_term`: a student with 1 A-to-F course and 1 failed
   pass/fail course. Assert `gpa_y1` reflects only the A-to-F course, and
   `n_failing_y1` equals 1.
1. `int_powerschool__gpa_cumulative`: the same student. Assert
   `earned_credits_cum_projected` includes the pass/fail credits when passed,
   and that `cumulative_y1_gpa_projected` and
   `potential_gpa_credits_cum_projected` exclude them.
1. `base_powerschool__sections`: a section with `gradescaleid = 0` inherits the
   course scale, and a section with a non-zero scale overrides it.

### Standard checks

- `dbt build --select base_powerschool__sections+` in one district, then
  `kipptaf`.
- `trunk check --force` on every changed file, run from inside the worktree.
  Markdownlint fires only at pre-push and CI, so check this spec too.
- After dbt Cloud CI passes, fetch warnings with `warning_only=true` before
  declaring done.

## Open items

1. **Tableau workbooks.** About 13 `rpt_*` and `int_tableau__*` models expose
   the flag as a dimension. Whether any workbook filters or calculates on it is
   unverified, and a workbook that does would need editing. This needs a
   dashboard owner to confirm, or a query against the Tableau metadata API.
1. **Paterson grade scale.** Someone must create a scale named `Pass Fail Scale`
   in the Paterson PowerSchool instance before any pass/fail course is set up
   there. Without it `is_pass_fail` is always `false` and Paterson pass/fail
   courses silently behave like today.
1. **Column name.** `is_graded_course` versus `is_academic_course`. Not
   blocking.

## Risks

- **Section-level override widens the GPA surface.** Once a section carries its
  own scale, GPA moves for those students. That is intended, but it will not
  happen on the commit that ships it, so the warn test is the only signal. If
  the test is ignored, a GPA shift could land unnoticed.
- **The rename touches contracts.** `gradescaleid_unweighted_resolved` changes 4
  `properties/*.yml` files. Contract enforcement matches on name and type, so a
  missed file fails the build loudly rather than silently. That is the good
  failure mode.
- **Snapshot history.** `int_powerschool__gpa_cumulative` is snapshotted.
  `n_failing_y1` and the projected-credit columns will show a step change on the
  first run after commit 2 for any student with a pass/fail enrollment. Anyone
  comparing snapshot history across that date needs to know why.
