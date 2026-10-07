# Focus course enrollments into the kipptaf network layer

Design for PR 1 of [#4925](https://github.com/TEAMSchools/teamster/issues/4925).
Covers the course-enrollments half only. The report-card-grades half (PRs 2
and 3) is out of scope here and stays blocked on an external Focus support
answer.

## Problem

Miami contributes zero course-enrollment rows to the kipptaf network layer for
AY2026. `base_powerschool__course_enrollments` and `base_powerschool__sections`
still union the frozen `kippmiami_powerschool` archive as their Miami branch,
and that archive stops at AY2025.

Measured 2026-08-25:

| `_dbt_source_relation`     | `base_powerschool__course_enrollments` AY2026 |
| -------------------------- | --------------------------------------------- |
| `kippnewark_powerschool`   | 44,481                                        |
| `kippcamden_powerschool`   | 14,655                                        |
| `kipppaterson_powerschool` | 3,947                                         |
| `kippmiami_powerschool`    | 0 (17,065 in AY2025)                          |

Focus has the data. The kipptaf `int_focus__schedule` wrapper carries 19,295
rows across 1,694 students, and is already declared in
`kipptaf/models/focus/sources-kippmiami.yml` with a kipptaf wrapper in place.

### The non-obvious half of the problem

Wiring a Focus branch into the base models is not sufficient.
`dim_student_section_enrollments` joins course enrollments to the student stint
on PowerSchool internal ids:

```sql
on cc.cc_studentid = enr.studentid
and cc.sections_schoolid = enr.schoolid
and cc.cc_yearid = enr.yearid
```

Every one of Miami's 1,757 AY2026 rows in
`int_students__student_enrollment_union` carries a null `studentid` and a null
`yearid`. The Focus branch never populated them, because they are PowerSchool
internals with no Focus equivalent. Null does not equal null, so a correct Focus
branch upstream still produces a null `student_enrollment_key` on every Miami
row. The dim would gain rows that are orphaned from the student dimension: a
silent failure, not a loud one.

## Approach

Follow the precedent set by the enrollment phase.
`base_powerschool__student_enrollments` at kipptaf is now a one-line
compatibility passthrough over `int_students__student_enrollments`, with
consumer migration deferred to
[#3999](https://github.com/TEAMSchools/teamster/issues/3999).

That precedent matters here because `base_powerschool__course_enrollments` has
more than 50 kipptaf consumers. Repointing them in this PR would be an enormous
diff, and [#2541](https://github.com/TEAMSchools/teamster/issues/2541) plans to
rename these models anyway. Passthroughs mean the Focus branches are written
once, not churned twice.

### Models

Five files change. Two are new, two become compatibility passthroughs, and one
consumer changes.

**New: `int_students__course_enrollments`** in
`kipptaf/models/students/intermediate/`.

```sql
with
    powerschool_conformed as (
        -- today's kipptaf base_powerschool__course_enrollments body,
        -- with Miami year-scoped out
        ...
    ),
    focus_conformed as (
        -- int_focus__schedule, renamed to the cc_* / sections_* contract
        ...
    )

select *, from powerschool_conformed

full union all corresponding

select *, from focus_conformed
```

**New: `int_students__course_sections`**, same shape. Its Focus branch reads
`stg_focus__course_periods`, which is at course-period grain, rather than
`int_focus__schedule`, which is at student grain.

**Changed: `base_powerschool__course_enrollments` and
`base_powerschool__sections`** at kipptaf become one-line passthroughs carrying
the same comment `base_powerschool__student_enrollments` uses.

**Changed: `dim_student_section_enrollments`** reads
`int_students__course_enrollments` directly, and its stint join moves to the
neutral key.

### Year-scoping, not exclusion

`int_students__student_enrollment_union` excludes Miami from the PowerSchool
side wholesale, because Focus carries enrollment history back to AY2018. Course
enrollments cannot do that. All 19,295 `int_focus__schedule` wrapper rows are
AY2026, and the archive holds Miami AY2020 through AY2025.

So the union is year-scoped, and the boundary is derived from the years Focus
actually covers rather than hardcoded:

```sql
where not (
    _dbt_source_project = 'kippmiami'
    and cc_academic_year >= (select min(academic_year) from int_focus__schedule)
)
```

This is the rule the attendance phase settled in the design comment on
[#4924](https://github.com/TEAMSchools/teamster/issues/4924). Hardcoding 2026
would silently break the first time Focus backfills an earlier year.

### Altitude

The Focus branch lives at kipptaf, not in the focus package. The #4924 rule is
to branch at the altitude PowerSchool derives the model, so that hashes are not
recomputed at network altitude. That rule is satisfied here: both branches are
already derived at package altitude, their union is inherently network altitude
because that is where the two sources meet, and no surrogate key is recomputed.
Every key in scope is generated downstream in `dim_student_section_enrollments`.

## Column mapping

All coverage figures measured 2026-08-25 against prod.

| Target column         | Focus source                                                                        | Coverage                              |
| --------------------- | ----------------------------------------------------------------------------------- | ------------------------------------- |
| `cc_dcid`             | `student_schedule_id`                                                               | 19,295 of 19,295 unique (post-dedupe) |
| `cc_dateenrolled`     | `start_date`                                                                        | native                                |
| `cc_dateleft`         | `end_date`                                                                          | native                                |
| `teachernumber`       | `teacher_id` to `int_focus__users.staff_id`, then roster `ein` coalesced with email | 77 of 77                              |
| `is_homeroom`         | `course_title like 'Homeroom%'`                                                     | 1,072 rows, elementary only           |
| `_dbt_source_project` | literal `kippmiami`                                                                 | n/a                                   |

### Homeroom

Focus carries a `homeroom` boolean on both the course and the schedule, and it
is null on every one of the 19,295 rows. `int_focus__advisory` already hit this
and identifies the homeroom course by title instead, so this reuses that rule:
`course_title like 'Homeroom%'`.

That makes `is_homeroom` a column on the neutral model rather than something
`dim_student_section_enrollments` derives. The dim computes it today as
`cc_course_number like 'HR%'`, a PowerSchool naming convention that Focus course
numbers do not follow. Each branch supplies its own rule and the dim reads the
column.

Coverage is elementary-only: 1,072 homeroom rows, concentrated in grades K
through 5. That is Focus configuration rather than a modeling gap, and is
already tracked on #4868.

### Grain

The kipptaf wrapper `int_focus__schedule` is one row per student per course
period: 19,295 rows. The `kippmiami_focus` package model underneath holds
19,594, and the wrapper deduplicates the 299-row difference on
`(student_id, course_period_id)`, keeping the open stint. Its own comment gives
the reason: Focus schedules some students into the same course period twice, a
same-day-superseded stint (`start_date = end_date`) alongside the current open
one.

Branch at the wrapper, which is what every kipptaf model reads. Expect 19,295
Focus rows, not 19,594 — a validation written against the package model's count
reads as a 299-row loss that is not happening.

`student_schedule_id` is unique across all 19,295 wrapper rows, so it seeds
`cc_dcid` cleanly and the surrogate key stays one-per-row.

### The stint join key

`dim_student_section_enrollments` moves from `(studentid, schoolid, yearid)` to
`(student_number, schoolid, academic_year)`.

This is behavior-preserving for the three NJ regions. The two keys have
identical selectivity:

| Region         | Rows   | Distinct on the PowerSchool-internal key | Distinct on the neutral key |
| -------------- | ------ | ---------------------------------------- | --------------------------- |
| `kippnewark`   | 98,162 | 98,156                                   | 98,156                      |
| `kippcamden`   | 23,955 | 23,954                                   | 23,954                      |
| `kipppaterson` | 2,086  | 2,085                                    | 2,085                       |

It also removes the PowerSchool coupling that the SIS-neutral decision exists to
shed.

### Teacher identity

`lead_teacher_staff_key` was the other candidate for a silent orphan, and it is
not one. All 77 teachers on the Focus schedule resolve to an `int_focus__users`
row on `staff_id`, and all 77 reach a staff-roster `employee_number` through
`ein` coalesced with email. For comparison, the NJ PowerSchool branch resolves
538 of 540.

All 77 also carry a `powerschool_teacher_number` on the staff roster, so the
Focus branch populates `teachernumber` from that column and the dim's existing
teacher join needs no change.

That holds because every current Miami teacher predates the Focus migration. A
future Miami-only hire would have no `powerschool_teacher_number`, so this gets
a warn-severity test rather than being assumed permanent.

## Columns that land null

`is_dropped_section`, `is_dropped_course`, and the NJ crosswalk columns (`cx.*`,
`illuminate_subject_area`) have no Focus source and land null on the Focus
branch, each carrying a `TODO` comment that points at the follow-up issue.

PowerSchool derives the two drop flags from its `sectionid < 0` convention,
which Focus has no equivalent of. Null rather than false, so Miami is excluded
from network drop-rate metrics rather than diluting them with 19,295
guaranteed-false rows. This is the treatment #4924 gave the six Miami attendance
flags, for the same reason.

The NJ crosswalk columns are New Jersey state reporting fields. Miami is
Florida, so they are correctly null rather than missing.

## Testing

- Uniqueness on `(cc_dcid, _dbt_source_project)` for
  `int_students__course_enrollments`.
- Uniqueness on the key of `int_students__course_sections`.
- NJ parity: `count(*)` and `count(distinct format('%T|%T', ...))` on the key
  columns, identical to prod for all three NJ regions, at both new models and at
  `dim_student_section_enrollments`.
- Miami AY2026 rows present in `dim_student_section_enrollments` with a non-null
  `student_enrollment_key`. This is the specific failure the join-key change
  fixes, and a row-count check alone would not catch it.
- Miami AY2020 through AY2025 row counts unchanged against the archive, proving
  the year-scoped union did not delete history.
- Warn-severity test: Focus schedule teachers with no resolvable
  `powerschool_teacher_number`.
- `dbt build --empty` across the descendant graph.

## Out of scope

- Report card grades, and the `DT` versus `DY` token question. PRs 2 and 3 on
  #4925.
- Gradebook grades. `int_focus__gradebook_grades` holds 3,232 rows across 1,066
  students as of 2026-08-25. Real and growing, but too thin for NJ-parity
  validation to mean anything.
- `student_standard_grades`, which is still empty upstream.
- Migrating the 50-plus consumers off the passthroughs. That is #3999.

## Prerequisite

Open the follow-up issue for the null drop-flag columns before implementation
starts. Its number fills the `TODO` comments on the Focus branch, so the code
cannot be written honestly without it.
