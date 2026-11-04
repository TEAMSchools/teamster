# End Focus seats on the withdrawal date — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Miami (Focus) course seats end no later than the student's withdrawal,
and seats that start after it disappear, matching NJ.

**Architecture:** The Focus package model `int_focus__schedule` gains
`effective_end_date` and drops seats that start after the student's enrollment
end at that school and year. kipptaf's `int_students__course_enrollments` builds
`exit_date` from the new column. One PR, using the existing `zz_stg_` branch on
`kippmiami_focus`.

**Tech Stack:** dbt (BigQuery), dbt unit tests, BigQuery MCP for verification.

**Spec:**
`docs/superpowers/specs/2026-10-22-focus-seat-withdrawal-end-design.md`

## Global Constraints

- `end_date` on `int_focus__schedule` stays the raw Focus value.
- New column is in Focus's last-day-enrolled convention. kipptaf adds 1 day for
  `exit_date`, as it already does for `cc_dateleft`.
- `is_dropped_section` and `cc_dateleft` in kipptaf keep reading raw `end_date`.
- The enrollment end for a student, school and `syear` is null when any of that
  student's enrollments there that year is open, else the latest `end_date`.
- A seat is removed only when its `start_date` is after that enrollment end. A
  seat starting on the end date is kept.
- A seat with no enrollment row at its school and year is kept unchanged.
- None of the other kipptaf consumers of `int_focus__schedule`
  (`int_focus__advisory`, `int_students__final_grades`,
  `int_students__course_sections`, `int_students__teacher_grade_levels`,
  `rpt_littlesis__enrollments`, `bridge_course_section_teachers`) reads seat
  `end_date`; they change only by losing removed rows. No edits there.
- Before any local dbt build, invoke the `dbt-local-dev` skill for target,
  `--defer` and `--state` flags. `--target staging` builds are shared writes:
  ask the user first, and run them in their own Bash call.

## Review Focus

1. A student still enrolled (open enrollment) keeps every seat to its term end.
   Pinned in Task 1 (student 21).
2. A student who withdrew and came back to the same school, still enrolled, is
   not clamped at the first exit. Pinned in Task 1 (student 22).
3. A seat that starts on the withdrawal day is kept and ends that day. Pinned in
   Task 1 (seat 14).
4. A real mid-term drop keeps its own earlier end date, and kipptaf still flags
   it dropped. Pinned in Task 1 (seat 12) and checked in Task 2 step 4.
5. A student whose only open seats all start after the withdrawal loses them,
   which leaves no open seat, so kipptaf's withdrawal-sweep rule reads their
   real drops as not dropped. Measured in Task 2 step 4; report the count, do
   not fix in this PR.

---

### Task 1: `effective_end_date` and seat removal in the Focus package

**Files:**

- Modify: `src/dbt/focus/models/intermediate/int_focus__schedule.sql`
- Modify: `src/dbt/focus/models/intermediate/properties/int_focus__schedule.yml`
- Test: `src/dbt/focus/models/intermediate/unit_tests.yml`

**Interfaces:**

- Produces: `int_focus__schedule.effective_end_date` (`date`, never null when
  `end_date` or `marking_period_end_date` is set). Row set excludes seats that
  start after the enrollment end.

- [ ] **Step 1: Write the failing unit test**
      `test_int_focus__schedule_ends_seats_at_withdrawal`

Inputs, `format: sql`, every column of each mocked ref (copy the column lists
from `test_int_focus__schedule_one_stint_per_course_period`; nulls except the
columns below):

- `stg_focus__marking_periods`: one row, `marking_period_id` 502, `syear` 2026,
  `school_id` 100, `type` `'semester'`, 2026-08-12 to 2027-01-15.
- `stg_focus__course_periods`: ids 30 to 34. `stg_focus__courses`: id 20.
- `stg_focus__schedule`, all `syear` 2026, `school_id` 100, `course_id` 20,
  `marking_period_id` 502, `mp` `'SEM'`:

| id  | student_id | course_period_id | start_date | end_date   |
| --- | ---------- | ---------------- | ---------- | ---------- |
| 11  | 20         | 30               | 2026-08-12 | null       |
| 12  | 20         | 31               | 2026-08-12 | 2026-09-29 |
| 13  | 20         | 32               | 2026-10-20 | null       |
| 14  | 20         | 33               | 2026-10-16 | null       |
| 15  | 21         | 30               | 2026-08-12 | null       |
| 16  | 22         | 30               | 2026-08-12 | null       |
| 17  | 23         | 30               | 2026-08-12 | null       |

- `stg_focus__student_enrollment`, `syear` 2026:

| id  | student_id | school_id | start_date | end_date   |
| --- | ---------- | --------- | ---------- | ---------- |
| 1   | 20         | 100       | 2026-08-13 | 2026-10-16 |
| 2   | 21         | 100       | 2026-08-13 | null       |
| 3   | 22         | 100       | 2026-08-13 | 2026-09-01 |
| 4   | 22         | 100       | 2026-09-15 | null       |
| 5   | 23         | 200       | 2026-08-13 | 2026-09-01 |

Expect (columns `student_schedule_id`, `end_date`, `effective_end_date`; seat 13
absent):

| student_schedule_id | end_date   | effective_end_date |
| ------------------- | ---------- | ------------------ |
| 11                  | null       | 2026-10-16         |
| 12                  | 2026-09-29 | 2026-09-29         |
| 14                  | null       | 2026-10-16         |
| 15                  | null       | 2027-01-15         |
| 16                  | null       | 2027-01-15         |
| 17                  | null       | 2027-01-15         |

Also add an empty `stg_focus__student_enrollment` input (`format: sql`,
`select ... where false`) to the two existing `int_focus__schedule` unit tests.
Their `expect` blocks stay as they are: an `expect` lists only the columns it
asserts.

- [ ] **Step 2: Run it and confirm it fails**

Run the model's unit tests through `kippmiami` (flags per `dbt-local-dev`):
`uv run dbt test --select "int_focus__schedule,test_type:unit" --project-dir src/dbt/kippmiami --target dev 2>&1 | tail -n 30`
Expected: the new test FAILS (unknown column `effective_end_date` or row 13
present); the two existing tests pass or fail only on the missing input.

- [ ] **Step 3: Implement in `int_focus__schedule.sql`**

- New CTE `enrollment_end` over `ref("stg_focus__student_enrollment")`, grouped
  by `student_id, school_id, syear`:
  `if(countif(end_date is null) > 0, null, max(end_date)) as enrollment_end_date`.
- Wrap the existing `dbt_utils.deduplicate(...)` call, unchanged, in a CTE
  (`deduplicated`).
- Final select: `deduplicated` left-joined to `enrollment_end` on `student_id`,
  `schoolid = school_id`, `academic_year = syear`. Project every existing
  column, then
  `(select min(d) from unnest([end_date, marking_period_end_date, enrollment_end_date]) as d) as effective_end_date`.
- `where e.enrollment_end_date is null or s.start_date <= e.enrollment_end_date`.
- One-line comment on the filter: seats Focus scheduled after the student left.

- [ ] **Step 4: Update `int_focus__schedule.yml`**

- Model `description`: add that seats starting after the student's last
  enrollment end at that school and year are excluded.
- New column `effective_end_date`: the last day the student is in the section —
  the earliest of `end_date`, `marking_period_end_date`, and the student's
  enrollment end at that school and year (null while any enrollment there is
  open). Last-day-enrolled convention, like `end_date`.

- [ ] **Step 5: Run unit tests and confirm all pass**

Same command as step 2. Expected: all 3 `int_focus__schedule` unit tests PASS.

- [ ] **Step 6: Build the model to dev and check row counts**

`uv run dbt build --select int_focus__schedule --project-dir src/dbt/kippmiami --target dev ...`
(defer flags per `dbt-local-dev`). Then via BigQuery MCP compare the dev table
with prod `kippmiami_focus.int_focus__schedule` for `academic_year = 2026`: dev
row count = prod minus the removed seats; `effective_end_date` null count equals
prod's count of rows with both `end_date` and `marking_period_end_date` null.

- [ ] **Step 7: Lint and commit**

`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <the 3 files> </dev/null`
from the worktree, then `git add -u` and commit
`fix(focus): end schedule seats at the student's enrollment end`.

### Task 2: kipptaf reads the new column

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/intermediate/int_focus__schedule.sql`
  (comment only)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql`
  (`focus_conformed`, the `exit_date` expression and its comment block)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml`
  (`exit_date` description)

**Interfaces:**

- Consumes: `int_focus__schedule.effective_end_date` from Task 1.
- Produces: `int_students__course_enrollments.exit_date` for Focus rows =
  `effective_end_date` + 1 day.

- [ ] **Step 1: Wrapper comment**

Add a one-line SQL comment to the kipptaf `int_focus__schedule` wrapper saying
its columns come from the package model at compile time. This marks it
`state:modified` so CI rebuilds it with the new column.

- [ ] **Step 2: `exit_date` from the new column**

In `focus_conformed`, replace
`date_add(coalesce(s.end_date, s.marking_period_end_date), interval 1 day)` with
`date_add(s.effective_end_date, interval 1 day)`. Rewrite the comment block
above it to say: the package resolves the seat's last day from the drop, the
term end and the withdrawal; this shifts it to PowerSchool's day-after
convention. Keep `#5043`. Leave `cc_dateleft` and `is_dropped_section`
untouched.

Update the `exit_date` description: a Miami seat also ends when the student
withdraws, as a NJ seat does.

- [ ] **Step 3: Build to dev**

Build the kipptaf wrapper, `int_students__course_enrollments` and
`dim_student_section_enrollments` into dev, reading the Task 1 dev package table
(flags per `dbt-local-dev`). Expected: builds and their tests pass.

- [ ] **Step 4: Verify against prod**

BigQuery MCP, dev vs prod, AY2026:

- The #6091 reproduce query with the withdrawal date taken from
  `int_students__student_enrollment_union.exitdate` (max per student, school,
  year, where that max is on or before today): 0 Miami seats not dropped with
  `exit_date` after it. Prod baseline: 2,481.
- Miami `countif(is_dropped_section)`: dev = prod minus dropped seats among the
  removed rows. Report Review Focus #5's count: students whose dev
  `is_dropped_section` count fell compared with prod.
- NJ rows: identical count and identical `exit_date` checksum
  (`sum(unix_date(exit_date))`) dev vs prod.
- Re-run the #6085 validation (graded rows dropped from `fct_grades_term`) if
  `fct_grades_term` is in the dev build; otherwise note it for CI.

- [ ] **Step 5: Lint and commit**

trunk check on the 3 files, `git add -u`, commit
`fix(kipptaf): read Focus seat end from the withdrawal-aware column`.

### Task 3: Seed staging, push, open the PR

**Files:** none.

- [ ] **Step 1: Ask the user**, then, in its own Bash call:
      `uv run dbt build --select int_focus__schedule --project-dir src/dbt/kippmiami --target staging`
      Expected: `zz_stg_kippmiami_focus.int_focus__schedule` has
      `effective_end_date` (`INFORMATION_SCHEMA.COLUMNS`).

- [ ] **Step 2: Push and open the PR** from `.github/pull_request_template.md`,
      body `Closes #6091`, with the Task 2 step 4 numbers (counts only, no
      student values).

- [ ] **Step 3: Watch CI and process `claude-review`** per `pr-ci-review`.
