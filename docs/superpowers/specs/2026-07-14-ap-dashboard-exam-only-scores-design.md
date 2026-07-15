# AP dashboard: surface exam scores with no matching course enrollment

- **Issue:** [#4391](https://github.com/TEAMSchools/teamster/issues/4391)
- **Status:** Design
- **Date:** 2026-07-14

> **Amendment (pre-existing uniqueness warning):** a full dev build of the fixed
> model surfaced a WARN on the `subject_code` uniqueness test for 3 rows
> (academic_year 2021, three Newark students, `subject_code = '4'` / Calculus
> BC). Verified this is **pre-existing, not caused by this fix**: the current
> prod table already has the identical 3-row duplicate keyed on
> `(academic_year, student_number, ap_course_subject)` — each of these students
> has two separate PowerSchool course-enrollment rows both tagged
> `ap_course_subject = '4'` (a main "AP Calculus BC" section plus a companion
> "Math IV Calculus AP BC Recitation" section, distinct `course_number`s so
> `rn_course_number_year = 1` doesn't collapse them). The fix's
> `course_enrollments` CTE filters identically to the original model's `s` join,
> so this data-quality quirk carries forward unchanged. No action item for this
> fix; do not add defensive dedupe for it (matches this repo's standing
> convention for the similar `base_powerschool__course_enrollments` double-write
> issue, #3900/#3915 — downgrade/track, don't dedupe).

## Summary

`rpt_tableau__ap_assessment_dashboard`
([`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql`](../../../src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql))
silently drops a student's AP exam score whenever they have no matching
AP-tagged course enrollment for that subject. College Board doesn't require
course enrollment to sit an exam, so this is a real, expected scenario — not
every AP exam-taker has a matching PowerSchool course record. The fix
restructures the model's joins so the exam-score join no longer depends on a
course-enrollment match, adds a new grain key column, and adds a new dashboard
state for this case.

## Problem

The current join chain is:

```sql
from int_extracts__student_enrollments as e
left join base_powerschool__course_enrollments as s
    on e.studentid = s.cc_studentid
    and e.academic_year = s.cc_academic_year
    and s.ap_course_subject is not null
    and not s.is_dropped_section
left join stg_google_sheets__collegeboard__ap_course_crosswalk as x
    on s.ap_course_subject = x.ps_ap_course_subject_code
left join int_assessments__ap_assessments as a
    on e.academic_year = a.academic_year
    and e.student_number = a.powerschool_student_number
    and s.ap_course_subject = a.ps_ap_course_subject_code
```

The `a` (exam score) join predicate references `s.ap_course_subject`. Since `s`
only produces a row when the student has a matching AP-tagged course enrollment,
a student with no such enrollment gets `s` = NULL — which means the `a` join can
never fire either, even when the student genuinely has a score in
`int_assessments__ap_assessments` for that subject. The row isn't mislabeled;
it's invisible.

Found while auditing the 2025-2026 AP data pipeline (#4390): 3 exam-score rows
present in `int_collegeboard__ap_unpivot` were absent from the dashboard, each
tracing to this join structure rather than a data gap.

## Approach: subject-bridge CTE

Add a CTE that unions the distinct AP subject codes a student is associated
with, from either side — course enrollment or exam score — then join course
enrollment (`s`), the course-crosswalk (`x`), and exam scores (`a`)
independently off that bridge instead of chaining `a` through `s`:

```sql
subjects as (
    select distinct academic_year, student_number, ap_course_subject as subject_code
    from course_enrollments -- s, same filters as today: ap_course_subject is not null,
                            -- not is_dropped_section, rn_course_number_year = 1
    union distinct
    select distinct
        academic_year, powerschool_student_number as student_number,
        ps_ap_course_subject_code as subject_code
    from ap_assessments -- a, same filter as today: test_subject != 'Calculus BC: AB Subscore'
)

...

from e
left join subjects using (academic_year, student_number)
left join course_enrollments as s
    using (academic_year, student_number, subject_code) -- plus union_dataset_join_clause
left join ap_assessments as a
    using (academic_year, student_number, subject_code)
left join ap_course_crosswalk as x
    on subjects.subject_code = x.ps_ap_course_subject_code
    and x.data_source = 'CB File'
```

A non-participating HS student (no AP course, no AP exam) still gets exactly one
row — `subjects` has no match, so `s`/`a`/`x` all stay NULL, same as today. A
participant gets one row per distinct subject drawn from either source.

## New column: `subject_code`

The existing uniqueness test keys on
`(academic_year, student_number, ap_course_subject)`. `ap_course_subject` is
sourced only from `s` and can be NULL — once `a` no longer depends on `s`, two
exam-only rows in different subjects would both have `ap_course_subject = NULL`
and collide on the grain.

Rather than changing what `ap_course_subject` means (it stays
course-enrollment-only, exactly as today, including NULL when there's no
course), add a new column `subject_code` — the bridged value, populated for
every participant regardless of which side matched — and move the uniqueness
test onto it:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - academic_year
          - student_number
          - subject_code
```

## Display logic

`test_subject_area` gets a third branch, and `ap_course_name` falls back to the
exam's own crosswalk-resolved name (`a.ap_course_name`, already computed
upstream in `int_assessments__ap_assessments` independent of the course-side
crosswalk `x`) when there's no course-side match:

```sql
case
    when s.courses_course_name is null and a.test_name is null
    then 'Not applicable'
    when s.courses_course_name is not null and a.test_name is null
    then 'Took course, but not AP exam.'
    when s.courses_course_name is null and a.test_name is not null
    then 'Took AP exam, not enrolled in course.'
    else a.ap_course_name
end as test_subject_area,

coalesce(x.ap_course_name, a.ap_course_name, 'Not an AP course') as ap_course_name,
```

`course_name`, `expected_scope`, and `expected_test_type` are unchanged — they
stay `'Not applicable'` whenever there's no course enrollment, regardless of
exam status, since those fields describe course-side expectations.

## Testing plan

1. `dbt build --select rpt_tableau__ap_assessment_dashboard --target dev --defer --state <prod manifest>`
   to materialize the fix into a dev schema.
2. Spot-check the 3 known-affected students from #4391 in chat only (never in a
   committed file, per repo PII policy) — confirm each now appears with
   `test_subject_area = 'Took AP exam, not enrolled in course.'` and a populated
   `ap_course_name`.
3. **Prod vs. new-build row diff** — run via BigQuery MCP, comparing the dev
   build against the prod table. Prod's `ap_course_subject` stands in for the
   old grain key (pre-fix, that column _was_ the full grain), so this is
   apples-to-apples. **`subject_code`/`ap_course_subject` is NULL for every
   non-participating student, and SQL `NULL = NULL` never matches** — a plain
   equality join on the raw column makes every non-participant look like both an
   add and a delete. Coalesce both sides to a sentinel before joining:

   ```sql
   with
       prod as (
           select
               academic_year, student_number,
               ifnull(ap_course_subject, '__none__') as subject_code_key,
               test_subject_area
           from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard
       ),
       dev as (
           select
               academic_year, student_number,
               ifnull(subject_code, '__none__') as subject_code_key,
               test_subject_area
           from `teamster-332318`.<dev_schema>.rpt_tableau__ap_assessment_dashboard
       ),
       added as (
           select dev.*
           from dev
           left join prod
               on dev.academic_year = prod.academic_year
               and dev.student_number = prod.student_number
               and dev.subject_code_key = prod.subject_code_key
           where prod.student_number is null
       ),
       deleted as (
           select prod.*
           from prod
           left join dev
               on prod.academic_year = dev.academic_year
               and prod.student_number = dev.student_number
               and prod.subject_code_key = dev.subject_code_key
           where dev.student_number is null
       )
   select 'added' as change_type, test_subject_area, count(*) as row_count
   from added
   group by test_subject_area
   union all
   select 'deleted' as change_type, test_subject_area, count(*) as row_count
   from deleted
   group by test_subject_area
   order by change_type
   ```

   Dry-run validated against current prod data (2026-07-14): `added` = 245,
   entirely `'Took AP exam, not enrolled in course.'` rows, spanning many
   historical academic years, not just the 3 cases cited in #4391 — the bug has
   been silently dropping exam-only scores since before 2018, the fix isn't
   year-scoped. `deleted` = 119, entirely `'Not applicable'` rows.

   **A `deleted` row is not automatically a regression.** A student who was
   previously a total non-participant (`'Not applicable'`, one placeholder row)
   and turns out to have an exam-only score gets their placeholder row
   _replaced_ by a real subject row — that shows up as one `deleted` + one
   `added` for the same `(academic_year, student_number)`, not a net loss. Run
   this reconciliation before trusting the `deleted` count:

   ```sql
   select
       count(*) as deleted_rows,
       countif(a.student_number is not null) as accounted_for_by_an_added_row,
       countif(a.student_number is null) as true_regressions
   from deleted as d
   left join (select distinct academic_year, student_number from added) as a
       on d.academic_year = a.academic_year and d.student_number = a.student_number
   ```

   Expected outcome and follow-up:
   - `added` should be > 0 and, when grouped by `test_subject_area`, should
     consist entirely of `'Took AP exam, not enrolled in course.'` rows —
     anything else in that bucket needs a look before merging.
   - `true_regressions` (from the reconciliation query) must be **0**. Any row
     there means the restructured joins lost a row that used to show up for a
     student with no offsetting new row — a real regression, not an improvement
     — and blocks the fix until explained. (Validated 0/119 on current prod
     data.)
   - Cross-check: `count(dev) = count(prod) + added - deleted`.

## Scope

Distinct from two related issues also found during the #4390 audit:

- The `int_collegeboard__ap_unpivot` dedup bug (collapses multiple
  unresolved-crosswalk students into one row via `dbt_utils.deduplicate` on a
  shared NULL `powerschool_student_number`) — not tracked yet, not this fix.
- The PowerSchool AP-course-tagging gap tracked in #4390 — a data problem, not a
  join-structure problem, and separately owned.

This fix only changes join structure, adds one column, and adds one dashboard
state. It does not change how multiple exam attempts for the same subject are
deduplicated (`int_assessments__ap_assessments.rn_highest` is not filtered on
here, same as before this fix) — that's pre-existing behavior, out of scope.
