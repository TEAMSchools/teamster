# End Focus course seats on the student's withdrawal date

Refs #6091.

## Intent

When a Miami student withdraws, Focus leaves their course seats open, and the
warehouse extends each one to the end of its marking period. NJ seats end on the
withdrawal date. Miami should match NJ, for every consumer of the Focus
schedule, not only `int_students__course_enrollments`.

## What NJ does (the target)

PowerSchool ends a withdrawn student's seats on the exit date and does not mark
them dropped. `base_powerschool__course_enrollments` treats
`dateleft = exitdate` as not dropped; "dropped" means the student left one class
mid-term while still enrolled. NJ has almost no seats that start after a
withdrawal. `is_current_section_enrollment` keeps its NJ meaning: the most
recent seat in the course, not "active today".

## Goals

- A Miami seat that overlaps the student's enrollment ends no later than the
  student's last enrollment end date at that school that year.
- A Miami seat that starts after that date is removed.
- `is_dropped_section` keeps its meaning. A seat closed by a withdrawal is not
  dropped.
- One PR.

## Non-goals

- Students who withdraw and return to the same school (#5947). The clamp uses
  the last enrollment end of the year, so the gap between stints is unchanged.
- Seats at a campus where the student has no enrollment that year. They keep
  their current dates (see the orphan notes in
  `dim_student_section_enrollments`).
- The 37 student-section pairs that have both an open and an end-dated Focus
  row. The existing pick (open row first) stays; the clamp now bounds the open
  row.

## Approaches

- **A. Clamp in `int_students__course_enrollments`.** One kipptaf model. Misses
  the six other kipptaf consumers that read `int_focus__schedule` directly.
- **B. Clamp per enrollment stint.** Also fixes #5947, but needs a pick between
  overlapping stints (an A5 dedup in a domain model) and pulls in #5947's design
  questions.
- **C. Fix in the Focus package's `int_focus__schedule`, as a new column.**
  Picked. Every consumer gets the fix. Overwriting `end_date` instead was
  rejected: kipptaf's `is_dropped_section` separates a drop from a withdrawal by
  checking whether the student still has an open seat that year, so clamping
  every seat would flip real mid-term drops to not dropped, and the raw Focus
  value would be lost.

## Design

### Focus package: `int_focus__schedule`

- Join each seat to the student's enrollment end at the same Focus school and
  `syear`, from `stg_focus__student_enrollment`: the latest enrollment end, and
  null when any enrollment that year is still open.
- Add a column (working name `enrollment_end_date`, the builder may pick a
  better one): the earliest of `end_date`, `marking_period_end_date`, and that
  enrollment end. Same last-day-enrolled convention as Focus `end_date`.
  Enrollment `end_date` uses that convention too: Focus records attendance on
  it, and `int_students__student_enrollment_union` adds 1 day to reach
  PowerSchool's first-day-not-enrolled.
- Remove seats whose `start_date` is after the enrollment end.
- `end_date` stays the raw Focus value.
- Seats with no enrollment at that school and year are kept unchanged.
- Add the column to the properties YAML.

### kipptaf

- `int_focus__schedule` wrapper: a SQL comment edit, so CI rebuilds it and sees
  the new column.
- `int_students__course_enrollments`, `focus_conformed`: `exit_date` reads the
  new column plus 1 day. `cc_dateleft` and `is_dropped_section` are unchanged
  (they read raw `end_date`).
- The other wrapper consumers get the removed rows automatically. Each one that
  reads seat end dates is checked for whether it should switch to the new
  column.

### Shipping in one PR

`kippmiami_focus` already routes to `zz_stg_kippmiami_focus` under the staging
target. Before pushing, build the package model into it with
`uv run dbt build --select int_focus__schedule --project-dir src/dbt/kippmiami --target staging`.
This is a shared write and needs the user's go-ahead.

## Verification

- Reproduce query from #6091 (all 2,481 seats, not only the 749 that start
  before the exit): 0 Miami seats not dropped with `exit_date` after the
  withdrawal. Take the withdrawal from `int_students__student_enrollment_union`,
  whose `exitdate` is on the same first-day-not-enrolled convention as
  `exit_date`. `int_extracts__student_enrollments.exitdate` keeps each SIS's own
  convention by design; its `last_enrolled_date` is the cross-region column.
- `is_dropped_section` count for Miami unchanged.
- NJ rows unchanged.
- #6085 validation re-run (graded rows dropped from `fct_grades_term`).
- Miami attendance section share falls toward NJ's.

## Left to the builder

- The column name.
- Which of the six other consumers should read the new column.
