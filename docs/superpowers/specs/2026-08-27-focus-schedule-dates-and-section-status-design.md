# Focus schedule date semantics and Miami section-status flags

Design for #5002 and #4968, batched because both change the `focus_conformed`
CTE in `int_students__course_enrollments`.

## Problem

Two questions on the Focus branch of `int_students__course_enrollments`, both
left open when PR 1 of #4925 shipped.

**#5002.** 1,839 Miami AY2026 course enrollments attach to no student stint
because the schedule row falls outside the stint window. Whether that is a data
defect or a Focus dating convention decides the fix, and the two fixes are
opposite. Blocked until #4987 restored real marking-period bounds on every
schedule row, which it did (verified 2026-08-26).

**#4968.** `is_dropped_section` and `is_dropped_course` are null on every Miami
row, because PowerSchool derives both from its `sectionid < 0` convention and
Focus records nothing equivalent. Null was deliberate: `false` would have read
as a verified zero drop rate. The cost is that `course_enrollment_rank` in
`dim_student_section_enrollments` has a constant ordering term for Miami and
falls through to date tiebreakers.

## What a Focus schedule `start_date` means

It is the marking period's start date, not the day the student joined the
section.

Measured 2026-08-27 against `kipptaf_focus.int_focus__schedule`, Miami AY2026,
19,363 rows:

| Check                                       | Result         |
| ------------------------------------------- | -------------- |
| `start_date = marking_period_start_date`    | 17,564 (90.7%) |
| `start_date < marking_period_start_date`    | 0              |
| `start_date > marking_period_start_date`    | 1,799          |
| Distinct `start_date` values, whole year    | 16             |
| Distinct `marking_period_start_date` values | 3              |

Sixteen distinct dates across 19,363 rows settles it. Every Semester 2 row is
dated `2027-01-15`, the Semester 2 start — a date four months in the future, so
it cannot be an event date. The 1,799 later rows all fall between `2026-08-12`
and `2026-08-27`: mid-term adds, dated to the day the row was written.

### The mismatch mechanism is not the one #4970 hypothesized

#4970 proposed that a student enrolling mid-term gets a `cc_dateenrolled` before
their own stint entry, so the overlap legitimately fails. Zero rows do that.
Measured causes of the 1,886 same-school orphans:

| Cause                                                                    | Rows  |
| ------------------------------------------------------------------------ | ----- |
| Stint window is degenerate — `exitdate <= entrydate`                     | 1,332 |
| Schedule row closed on or before the stint entry                         | 478   |
| Future-term row (Semester 2, Quarter 2) for a student who already exited | 76    |
| `cc_dateenrolled < entrydate`                                            | 0     |

Seventy-one percent fail because the _stint_ has a zero-or-negative-length
window. No schedule date of any kind can overlap `entrydate <= d < exitdate`
when `exitdate <= entrydate`. That defect is Focus-only and new:

| Region         | AY2024 | AY2025 | AY2026               |
| -------------- | ------ | ------ | -------------------- |
| `kippmiami`    | 0      | 0      | 185 of 1,760 (10.5%) |
| `kippnewark`   | 0      | 0      | 0                    |
| `kippcamden`   | 0      | 0      | 0                    |
| `kipppaterson` | 0      | 0      | 0                    |

Ninety-one zero-length, 94 negative-length. Zero in Miami's PowerSchool archive
years, so it arrived with `int_focus__student_enrollment_roster`. This gets its
own issue; it is upstream of both #5002 and #4968.

The remaining 554 are correct nulls: a section closed before the student
arrived, or a future-term section for a departed student. Attaching either to
the stint would emit the confidently wrong `student_enrollment_key` that #4970
forbids.

**So the conforming is correct and the overlap predicate does not change.**
#5002 resolves as documentation plus a new tracker.

## The section-status signal

`is_dropped_section` is meant to catch a premature drop: a section the student
unenrolled from before its expected end date. Focus closes a schedule row by
setting `end_date`, and the row's expected end is its marking period's end.

```sql
s.end_date < s.marking_period_end_date
and countif(s.end_date is null) over (
    partition by s.student_id, s.academic_year
) > 0 as is_dropped_section
```

The surviving-open-section test excludes a withdrawal sweep. When a student
withdraws from school, Focus closes every one of their schedule rows at once;
that is a consequence of leaving, not a drop. It mirrors PowerSchool's own
`dateleft = exitdate` exclusion in `base_powerschool__course_enrollments`.

PowerSchool's second exclusion, `dateleft = max_calendardate` (a year-end
close), needs no equivalent: zero Focus rows have an `end_date` at or after
their marking period's end.

### Measured

576 of 19,363 AY2026 rows (2.97%) across 84 students — 484 same-day
unenrollments and 92 that ran a while before ending. `is_dropped_course` lands
at 119 rows.

Reconciled against a like-for-like NJ derivation, rebuilt from the raw
`sectionid` convention with the same withdrawal-sweep exclusion, at the same
point in the year:

| Region, AY2026 to date  | Rate  |
| ----------------------- | ----- |
| `kipppaterson`          | 0.23% |
| `kippnewark`            | 2.63% |
| `kippmiami` (this rule) | 2.97% |
| `kippcamden`            | 8.55% |

A stint-joined derivation of the same rule agrees on 19,358 of 19,363 rows. The
5 it over-flags are students holding an open section _and_ a section ending
exactly on their stint exit.

### Why not the alternatives

**A zero-length row is a drop, not an artifact.** An earlier draft excluded rows
where `start_date = end_date` on the grounds that no NJ row carries that shape
(verified: 0 of 2,492 flagged NJ AY2026 rows). But that is a fact about
PowerSchool's data, not a semantic boundary. On "unenrolled before the expected
end," a row that starts and ends the same day is the most premature drop there
is. Excluding them read 0.475%, well below every NJ region.

**No stint join.** Adding `int_students__student_enrollment_union` to
`focus_conformed` risks fanning out a schedule row when a student holds two
stints at one school-year, which would break the uniqueness test on
`(cc_dcid, _dbt_source_project)`. The window rule needs no join and agrees on
99.97% of rows.

**`is_dropped_course` needs its own CTE.** BigQuery does not allow a window
function inside another window function's argument, and `is_dropped_course`
windows over `is_dropped_section`.

## Changes

### `#5002` — documentation

| File                                                                                           | Change                                                                                                                                                                                         |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/focus/models/intermediate/properties/int_focus__schedule.yml`                         | `start_date` reads "First date the student is scheduled into the section." Replace with the term-start semantics and the evidence. Same for `end_date`.                                        |
| `src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql`            | Comment in `focus_conformed`: `cc_dateenrolled` and `cc_dateleft` are term dates, not event dates.                                                                                             |
| `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml` | Column docs for both dates and both flags.                                                                                                                                                     |
| `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`                  | The residual attribution credits "1,859 schedule rows fall outside a stint at the same school". Replace with the measured three-way split.                                                     |
| `src/dbt/kipptaf/tests/properties.yml`                                                         | Same correction to the orphan-rate test description, which credits "same-day stints and cross-school scheduling artifacts". Threshold stays at 15%: this change does not move the orphan rate. |

Column docs for `int_focus__schedule` live on the focus-package YAML, not the
kipptaf wrapper, which states so in its own description. The wrapper is consumed
via `source()`, but a description-only edit adds no column and changes no
values, so the two-PR sequencing rule does not apply.

### `#4968` — the two flags

`focus_conformed` gains `is_dropped_section` and drops its
`cast(null as bool) as is_dropped_course`. A follow-on CTE computes
`is_dropped_course`, mirroring PowerSchool's window — true only when every
section of the course is dropped for that student-year:

```sql
    focus_course_dropped as (
        select
            *,
            avg(if(is_dropped_section, 1, 0)) over (
                partition by
                    _dbt_source_project,
                    students_student_number,
                    cc_academic_year,
                    cc_course_number
            ) = 1.0 as is_dropped_course,
        from focus_conformed
    )
```

The final `full union all corresponding` reads `focus_course_dropped` instead of
`focus_conformed`. `corresponding` matches by name, so column order does not
matter.

New Jersey is untouched by construction: `powerschool_conformed` is not edited.

### New test

A warn-severity rate test on the Miami drop rate, mirroring the existing
orphan-rate test, so the NJ-band reconciliation survives past this PR rather
than living only in a comment.

## Downstream impact

Forty models filter with the bare idiom `where not is_dropped_section`. In SQL
`not null` is null and `where` treats null as false, so every Miami row is
currently removed wherever the idiom appears — cause 1 of #4973, tracked as
#4996. Non-null flags flip those 40 models from excluding every Miami row to
including 97% of them, before any of #4996's per-report scope decisions are
made.

#4996 anticipates this: "If #4968 yields non-null drop flags for Miami, the
coalesce becomes a no-op and this work shrinks to the scope decisions alone."
The measured impact gets commented there so those decisions happen with the
numbers in hand.

## Verification

- `dbt build --select int_students__course_enrollments+1` on the branch.
- NJ row counts and both flag distributions, PR schema against prod, per region.
  Must be row-identical.
- `dbt_utils.unique_combination_of_columns` on `(cc_dcid, _dbt_source_project)`.
  The new CTE is a window and cannot fan out, but the test proves it.
- Both flags non-null on 100% of Miami rows, with the section rate at 2.97%.
- `test_miami_section_enrollment_orphan_rate` still passes unchanged.

## Out of scope

- Widening the overlap predicate in `dim_student_section_enrollments`. #4970
  forbids it and the measurement removes the motive.
- The 185 degenerate stints. New issue, upstream of this work.
- The 186 cross-school orphans. #5003.
- The 40 downstream scope decisions. #4996.

Refs #5002 Refs #4968 Refs #4970
