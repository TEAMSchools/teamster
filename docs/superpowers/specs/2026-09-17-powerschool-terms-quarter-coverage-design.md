# PowerSchool terms quarter coverage

Design for [#5390](https://github.com/TEAMSchools/teamster/issues/5390).

## Problem

`int_students__attendance_daily` inner joins student membership days to
`int_students__terms` on a quarter-grain predicate. A membership day that no
quarter covers is dropped. 1,864,931 membership days are dropped today, about 11
percent of the 14,443,504 rows the model holds. Every dropped day is a real
student-day with a real attendance value, and the model feeds network attendance
reporting.

The issue proposed making the join a left join. That recovers the rows but gives
every one of them a null `term` and `semester`.

## Root cause

The quarters are missing, not merely unmatched.

`src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms.sql` derives
quarter dates only from `stg_powerschool__termbins`, inner joined to the school
year's year record:

```sql
from {{ ref("stg_powerschool__terms") }} as t
inner join
    {{ ref("stg_powerschool__termbins") }} as tb
    on t.id = tb.termid
    and t.schoolid = tb.schoolid
    and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
where t.isyearrec = 1 and t.schoolid != 0
```

94 quarters across 25 New Jersey school-years have no `termbins` row, so they
produce no quarter rows — even though `stg_powerschool__terms` carries their
`Q1` through `Q4` records, each with its own `firstday` and `lastday`. 21 of
those school-years have no quarter coverage at all today. By region: kippnewark
65 quarters across 17 school-years, kippcamden 29 across 8, kipppaterson none.

Classified by cause, the 1,864,931 dropped days are:

| Cause                               | Days      |
| ----------------------------------- | --------- |
| No quarter rows for the school-year | 1,723,230 |
| Day before the first quarter        | 50,737    |
| Day after the last quarter          | 69,664    |
| Day in a gap between quarters       | 21,300    |

So 92 percent of the loss is the coverage gap. The join type is what makes the
gap lossy; it is not what causes it.

Worked example, `kippnewark` schoolid 73255. For `yearid` 29 the `terms` table
holds `Q1` through `Q4` with contiguous dates from 2019-08-19 to 2020-06-13, and
`termbins` holds nothing. For `yearid` 35 both sources exist and their dates are
identical.

## The two quarter sources are not interchangeable

Where both sources exist they usually agree, but 143 quarters disagree on
`term_start_date` or `term_end_date`:

| Region         | Quarters in both | Dates disagree |
| -------------- | ---------------- | -------------- |
| `kippnewark`   | 483              | 76             |
| `kippcamden`   | 247              | 61             |
| `kipppaterson` | 16               | 6              |

A `union distinct` of the two sources therefore leaves two rows for a
disagreeing quarter, a membership day matches both, and the attendance model
fans out. Measured: the membership total rises from 16,035,288 to 17,835,466.

`termbins` stays authoritative because it is what every quarter in the model
resolves through today, so preferring it changes no value that currently exists.
The `terms` row fills only the school-years `termbins` never covered.

## Design

### 1. `int_powerschool__terms` gains a `terms`-sourced fallback

Package model, `src/dbt/powerschool/models/sis/intermediate/`.

Two quarter branches, combined with `union all`:

- The existing `termbins` branch, unchanged.
- A branch over `stg_powerschool__terms` rows whose `abbreviation` is `Q1`
  through `Q4`, taking `firstday` as `term_start_date`, `lastday` as
  `term_end_date`, and the `semester` column the staging model already derives.
  This branch is anti-joined against the `termbins` branch on
  `(schoolid, yearid, term)`, so it contributes only quarters `termbins` does
  not supply.

The anti-join is a `left join` plus a `where <termbins side> is null` in a
following CTE, not `qualify` and not a subquery, per `.claude/rules/dbt-sql.md`.

`is_current_term` on the fallback branch follows the existing expression,
`current_date` between the quarter's start and end dates.

The model's existing `unique_combination_of_columns(schoolid, yearid, term)`
test holds by construction: each branch is unique on that key, and the anti-join
makes them disjoint on it.

### 2. `int_students__attendance_daily` left joins the term spine

The `calcs` CTE's `inner join` to `int_students__terms` becomes a `left join`.
`and t.term is not null` stays in the `ON` clause, so the quarter-grain
restriction survives. In the projection:

```sql
mem.yearid + 1990 as academic_year,
```

`academic_year` comes from the membership row rather than the term spine,
because the left join nulls every term column on a day no quarter covers.
Neither union branch of the membership CTE carries an `academic_year` column, so
the arithmetic is the only available form. It is value-identical where the join
matches: `int_students__terms` keys `yearid` to `academic_year - 1990` on both
its branches, and the join matches on `mem.yearid = t.yearid`.

`t.term` and `t.semester` stay null on the residual rows. This is the backstop
for the 552,757 days that still match no quarter after change 1, not the primary
fix.

`academic_year` gains a `not_null` test, which the model does not have today.

### 3. Two `int_students__terms` defects

Both are inert today and both live in
`src/dbt/kipptaf/models/students/intermediate/int_students__terms.sql`.

`and p.rn = 1` sits inside a `FULL JOIN` `ON` clause, where it decides which
rows match rather than filtering `p`. A `p` row with `rn = 2` passes through as
a `p`-only row with every quarter column null. The fix filters `rn = 1` in a CTE
over `stg_powerschool__terms` that the join then reads. The rule in
`.claude/rules/dbt-sql.md` that `FULL JOIN` conditions referencing one side stay
in `ON` covers match conditions; `rn = 1` is a row filter, and sitting in `ON`
is exactly why it does nothing.

A `q`-only row from the same full join emits null for every `p` column,
including `_dbt_source_relation`, and downstream models `regexp_extract` a
region out of that column. The fix is
`coalesce(p._dbt_source_relation, q._dbt_source_relation)`, which requires
adding `_dbt_source_relation` to the `powerschool_quarters` CTE — it does not
select the column today.

### 4. Descriptions

`int_students__terms`'s description states that PowerSchool quarter dates
resolve "through termbins rather than the raw terms table's own quarter row".
After change 1 that is true only where `termbins` has rows, so the description
changes with the code.

## Measured effect

Membership days that match no quarter, prod, 2026-09-17:

| Region         | Today     | After change 1 | Recovered with a real term |
| -------------- | --------- | -------------- | -------------------------- |
| `kippnewark`   | 1,139,469 | 46,051         | 1,093,418                  |
| `kippcamden`   | 232,980   | 14,224         | 218,756                    |
| `kippmiami`    | 492,482   | 492,482        | 0                          |
| `kipppaterson` | 0         | 0              | 0                          |
| Total          | 1,864,931 | 552,757        | 1,312,174                  |

`int_students__attendance_daily` gains all 1,864,931 rows from change 2.
1,312,174 of them carry a real `Q1` through `Q4` term because of change 1, and
552,757 carry a null term.

Miami recovers nothing here. Its PowerSchool archive terms are not declared as a
kipptaf source, so `int_students__terms` carries only Focus-derived marking
periods for Miami. #4750 item 3 wires the archive's `stg_powerschool__terms`
into kipptaf and should recover part of the 492,482 with no further change to
these models. Re-run the reproduce query in #5390 after that merges.

## Blast radius

`int_powerschool__student_course_grades_spine`, in the same package, builds a
`term_spine` from `int_powerschool__terms` and inner joins it to course
enrollments on `(schoolid, yearid)`. A school-year that gains 4 quarters turns 1
spine row per course enrollment into 5. Measured on a local `kippnewark` dev
build, that is 143,635 added rows against 4,232,025 today, 3.4 percent, across
the 17 school-year pairs that gain quarters. Rows in every other school-year are
unchanged, at 3,090,648 on both sides.

Those rows are not padding. Every affected `yearid` has real quarter rows in
`stg_powerschool__storedgrades` — between 4,820 and 104,341 per year — and the
spine's quarter joins key on `(studentid, yearid, course_number, quarter)`
without `schoolid`, so the added rows land historical quarter grades that
currently have nowhere to go.

`int_powerschool__ada_term` groups on `semester` and `term`. It gains real term
rows rather than the single null-term group a left-join-only fix would have
created. Its grain is
`(_dbt_source_project, student_number, academic_year, term)` at
`severity: error`. A residual null-term row is safe on that grain because
`semester` and `term` both come from the left-joined term spine and go null
together, so each student-year yields at most one null-term group.

The year-level rollups are a different matter: they partition by
`(_dbt_source_project, student_number, academic_year)` with no semester or term,
so they do take in the recovered days. That is the fix working as intended —
those days are real membership the quarter join was discarding — but it means
year-level ADA figures move for the affected school-years, not just gain rows.

`rpt_tableau__attendance_dashboard` projects `term` and floors on
`calendardate >= '{{ var("current_academic_year") - 1 }}-07-01'`. The NJ
recovered days all predate that floor. Miami's `yearid` 35 runs 2025-08-12 to
2026-06-04, so 8,905 Miami days enter the dashboard with a null `term` until
#4750 item 3 lands.

`fct_student_attendance_enrollment_daily` reads `term` from
`int_students__enrollment_daily`, not from `int_students__attendance_daily`, so
the null term does not reach it. Its attendance measures do change, because
1,864,931 more student-days now carry an attendance value. That is the point of
the fix.

The remaining `int_students__terms` consumers — `rpt_illuminate__terms`,
`int_tableau__gradebook_audit_teacher_scaffold`, `rpt_tableau__gradebook_gpa`,
`rpt_tableau__student_course_grades`,
`int_extracts__course_enrollments_by_term`,
`int_extracts__course_schedule_by_term`,
`int_extracts__student_enrollments_subjects`, and
`int_students__enrollment_daily` — gain quarter rows for historical school-years
and need checking for grain and fan-out during implementation.

## Shipping

Change 1 is value-only: `int_powerschool__terms` gains rows, not columns. Per
`.claude/rules/dbt-models.md` a value-only package edit needs no `zz_stg_*`
staging, so all four changes ship in one PR. dbt Cloud CI compiles kipptaf
against the deferred staging environment, and the corrected values reach kipptaf
after the next prod rebuild.

## What fixed looks like

- The #5390 reproduce query returns 552,757 unmatched, down from 1,864,931. The
  residual is 492,482 Miami days plus 60,275 NJ days that fall outside every
  quarter's date range. That NJ figure is lower than the 91,795 NJ date-edge
  days counted above, because a `terms`-sourced quarter range does not always
  match the `termbins` range it replaces and absorbs some days the old ranges
  left outside.
- The membership total stays 16,035,288, proving no fan-out.
- `academic_year` is non-null on every `int_students__attendance_daily` row.
- `int_powerschool__terms`, `int_students__terms`, and
  `int_students__attendance_daily` keep their existing uniqueness tests at
  `severity: error`.
- `int_powerschool__student_course_grades_spine` grows by the measured count and
  its added rows carry non-null quarter grades.
