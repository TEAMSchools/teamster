# Focus Attendance and Gradebook Intermediate Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three remaining Focus intermediate models —
`int_focus__attendance_day`, `int_focus__attendance_period`, and
`int_focus__gradebook_grades` — adding the dlt ingestion the gradebook model
needs to reach a course period.

**Architecture:** Two attendance intermediates resolve `attendance_codes` and
ship immediately; they depend on nothing new. The gradebook intermediate needs
two Focus link tables that were never configured for extraction, so it is gated
behind a dlt config change, a Dagster branch-deployment load, and two new
staging models. All three models are staging columns plus resolved reference
attributes — none is the `__pivot` decode pattern, and no `__pivot` models are
created.

**Tech Stack:** dbt (BigQuery), Dagster + dlt, `uv` for all Python execution.

## Global Constraints

- **Worktree.** All work happens in
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-intermediates` on
  branch `cbini/feat/claude-focus-intermediates`. Use `git -C <worktree>` on
  every git call and `--project-dir <worktree>/src/dbt/focus` on every dbt call.
  Editing `/workspaces/teamster/<path>` instead silently dirties `main`.
- **Python.** Always `uv run` — never bare `python`, `dbt`, or `dagster`.
- **Design source of truth.**
  `docs/superpowers/specs/2026-08-18-focus-attendance-gradebook-intermediates-design.md`
- **Naming.** Intermediates rename `syear` to `academic_year` and `school_id` to
  `schoolid`, matching `int_focus__schedule` and
  `int_focus__report_card_grades`.
- **Staging models are contract-enforced** (set at the `staging` directory level
  in `dbt_project.yml`): every projected column needs a `data_type` in
  `properties/`, plus `unique` and `not_null` on the PK at `severity: error`.
- **Intermediate models are not contract-enforced** — properties carry
  descriptions and tests, no `data_type`.
- **Staging drops** dlt bookkeeping (`_dlt_*`) and the audit quad
  (`created_by_class`, `created_by_id`, `updated_by_class`, `updated_by_id`).
  `created_at` and `updated_at` are kept.
- **Soft delete.** Neither new source table has a `deleted` column, so neither
  gets a soft-delete filter.
- **PII.** `student_id` carries `config.meta.contains_pii: true`, and so does
  any free-text `comment` on a person-linked row. Focus `student_id` is the
  network student number prefixed with `8400`.
- **Lint.** Do not run `trunk fmt` / `trunk check` manually for code; the
  pre-commit hook formats and pre-push blocks. Markdown and SQL do need
  `.trunk/tools/trunk check --force --no-fix <files> </dev/null` run from inside
  the worktree before pushing, because sqlfluff and markdownlint fire only at
  pre-push and CI.

---

## File Structure

**Modified:**

- `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml` — two new
  table entries
- `src/dbt/focus/models/staging/sources-bigquery.yml` — two new source
  declarations with Dagster asset keys

**Created — staging:**

- `src/dbt/focus/models/staging/stg_focus__gradebook_assignments_join_course_periods.sql`
- `src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml`
- `src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types_join_course_periods.sql`
- `src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types_join_course_periods.yml`

**Created — intermediate:**

- `src/dbt/focus/models/intermediate/int_focus__attendance_day.sql`
- `src/dbt/focus/models/intermediate/properties/int_focus__attendance_day.yml`
- `src/dbt/focus/models/intermediate/int_focus__attendance_period.sql`
- `src/dbt/focus/models/intermediate/properties/int_focus__attendance_period.yml`
- `src/dbt/focus/models/intermediate/int_focus__gradebook_grades.sql`
- `src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml`

---

## Task 1: Configure dlt ingestion for the two gradebook link tables

Adds the two Focus tables to the dlt pull and declares them as dbt sources.
Pushing this task is what creates the Dagster branch deployment that Task 4
loads from.

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`
- Modify: `src/dbt/focus/models/staging/sources-bigquery.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: BigQuery tables
  `dagster_kippmiami_dlt_focus.gradebook_assignments_join_course_periods` and
  `dagster_kippmiami_dlt_focus.gradebook_assignment_types_join_course_periods`,
  reachable in dbt as `source("focus", "<table>")`.

- [ ] **Step 1: Add the two table entries to the dlt config**

In `focus.yaml`, immediately after the `gradebook_templates` entry (the last
entry in the Gradebook block), add:

```yaml
- table_name: gradebook_assignments_join_course_periods
  cursor_column: updated_at
- table_name: gradebook_assignment_types_join_course_periods
  cursor_column: updated_at
```

`cursor_column: updated_at` is verified, not assumed — both tables carry
`updated_at :: timestamp with time zone`. Do NOT add
`gradebook_deleted_assignments_join_course_periods`.

- [ ] **Step 2: Confirm the existing test still passes**

`tests/libraries/test_dlt_focus_kippmiami_schedule_wiring.py` derives its
expectation from the config where `cursor_column is None`. Both new entries
declare a cursor, so the expected set is unchanged.

Run:
`uv --directory <worktree> run pytest tests/libraries/test_dlt_focus_kippmiami_schedule_wiring.py -v`

Expected: PASS.

- [ ] **Step 3: Declare the two dbt sources**

In `sources-bigquery.yml`, after the `gradebook_templates` entry and before the
`# Discipline` comment, add:

```yaml
- name: gradebook_assignments_join_course_periods
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - dlt
          - focus
          - gradebook_assignments_join_course_periods
- name: gradebook_assignment_types_join_course_periods
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - dlt
          - focus
          - gradebook_assignment_types_join_course_periods
```

- [ ] **Step 4: Verify dbt parses the new sources**

Run: `uv run dbt parse --project-dir <worktree>/src/dbt/focus`

Expected: parses without error. A source declared but not yet referenced by any
model is inert — dbt does not check that the BigQuery table exists.

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml src/dbt/focus/models/staging/sources-bigquery.yml
git -C <worktree> commit -m "feat(kippmiami): ingest Focus gradebook course-period link tables

The tables linking a gradebook assignment and assignment type to a course
period exist in Focus but were never configured for extraction, so a gradebook
grade could not reach its course. Both carry updated_at, so both probe on the
standard cursor.

Refs #4865"
```

---

## Task 2: `int_focus__attendance_day`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__attendance_day.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__attendance_day.yml`

**Interfaces:**

- Consumes: `stg_focus__attendance_day`, `stg_focus__marking_periods`,
  `stg_focus__attendance_codes`.
- Produces: PK `student_attendance_day_id`. Grain is one row per student per
  school date. Exposes `schoolid`, `academic_year`, `state_value`, and
  `daily_code_*` resolved code attributes.

- [ ] **Step 1: Write the properties file with the grain test**

Create `properties/int_focus__attendance_day.yml`:

```yaml
models:
  - name: int_focus__attendance_day
    description: >-
      Focus daily attendance with the daily attendance code resolved to its
      title and excused/tardy flags, plus marking-period context — one row per
      student per school date, the same grain as stg_focus__attendance_day.
      state_value is the present/absent classification; the code join supplies
      the reason for an absence, not the classification itself. daily_code holds
      an attendance_codes short_name rather than an id, and codes are scoped per
      school per year, so school is resolved from the marking period before the
      code join. No attendance_calendar join — its minutes column is a single
      sentinel value and detecting missing attendance records needs an
      enrollment-by-calendar-day scaffold at a different grain. Internal-only —
      a rpt_ view must sit between this model and any external consumer.
    columns:
      - name: student_attendance_day_id
        description: >-
          Primary key — Focus attendance_day id; one row per student per school
          date.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: academic_year
        description: >-
          Focus school year start year the attendance was taken in (e.g. 2026 =
          2026-27).
      - name: schoolid
        description: >-
          Focus school id, resolved from the marking period because
          attendance_day carries no school_id of its own. Null on the few rows
          whose marking_period_id does not resolve.
      - name: student_id
        description: >-
          Focus student id. Note this is the network student number prefixed
          with `8400` (Miami-Dade's FLDOE district number), not the bare student
          number.
        config:
          meta:
            contains_pii: true
      - name: school_date
        description: Calendar date the attendance was recorded for.
      - name: marking_period_id
        description: Focus marking-period id the school date falls in.
      - name: daily_code
        description: >-
          Raw daily attendance code as an attendance_codes short_name (U, AE,
          AD). Null when the student was present.
      - name: state_value
        description: >-
          Present/absent classification — 1 present, 0 absent. Populated on
          every row and independent of daily_code.
      - name: minutes_present
        description: Minutes the student was present for the day.
      - name: minutes_absent
        description: Minutes the student was absent for the day.
      - name: time_in
        description: Time the student arrived, where recorded.
      - name: time_out
        description: Time the student left, where recorded.
      - name: comment
        description: Free-text comment on the day's attendance.
        config:
          meta:
            contains_pii: true
      - name: note_approved
        description: Whether an attached attendance note was approved.
      - name: note_message
        description: Free-text message on an attached attendance note.
        config:
          meta:
            contains_pii: true
      - name: notified_callouts
        description: Callout notifications sent for the day's attendance.
      - name: admin_user_id
        description: Focus user id of the administrator who recorded the row.
      - name: last_updated_user
        description: Identifier of the user who last updated the row.
      - name: last_updated_date
        description: Source last-updated timestamp.
      - name: imported
        description: Y/N — whether the attendance row was imported.
      - name: daily_code_id
        description: >-
          Focus attendance_codes id the daily_code short name resolved to, for
          the row's school and year.
      - name: daily_code_title
        description: >-
          Readable daily attendance code name (Absent Unexcused, Absent Excused,
          Absent Documented).
      - name: daily_code_type
        description: >-
          Whether the code is teacher-entered or official (office-entered).
      - name: daily_code_state_code
        description: State-reported attendance code — P present, A absent.
      - name: daily_code_excused
        description: Y when the absence is excused.
      - name: daily_code_tardy
        description: Y when the code represents a tardy.
      - name: daily_code_chronic_absenteeism
        description: Whether the code counts toward chronic absenteeism.
      - name: daily_code_truancy
        description: Whether the code counts toward truancy.
      - name: daily_code_state_attendance_type
        description: State attendance type the code reports under.
      - name: marking_period_title
        description: Marking-period name from stg_focus__marking_periods.
      - name: marking_period_short_name
        description: Abbreviated marking-period name.
      - name: marking_period_type
        description: >-
          Marking-period granularity (year, semester, quarter, progress period).
      - name: marking_period_start_date
        description: First date of the marking period.
      - name: marking_period_end_date
        description: Last date of the marking period.
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select int_focus__attendance_day`

Expected: FAIL — the model file does not exist yet, so dbt reports the node is
missing.

- [ ] **Step 3: Write the model**

Create `int_focus__attendance_day.sql`:

```sql
select
    ad.id as student_attendance_day_id,
    ad.syear as academic_year,
    ad.student_id,
    ad.school_date,
    ad.marking_period_id,
    ad.daily_code,
    ad.state_value,
    ad.minutes_present,
    ad.minutes_absent,
    ad.time_in,
    ad.time_out,
    ad.comment,
    ad.note_approved,
    ad.note_message,
    ad.notified_callouts,
    ad.admin_user_id,
    ad.last_updated_user,
    ad.last_updated_date,
    ad.imported,

    mkp.school_id as schoolid,
    mkp.title as marking_period_title,
    mkp.short_name as marking_period_short_name,
    mkp.type as marking_period_type,
    mkp.start_date as marking_period_start_date,
    mkp.end_date as marking_period_end_date,

    ac.id as daily_code_id,
    ac.title as daily_code_title,
    ac.type as daily_code_type,
    ac.state_code as daily_code_state_code,
    ac.excused as daily_code_excused,
    ac.tardy as daily_code_tardy,
    ac.chronic_absenteeism as daily_code_chronic_absenteeism,
    ac.truancy as daily_code_truancy,
    ac.state_attendance_type as daily_code_state_attendance_type,

from {{ ref("stg_focus__attendance_day") }} as ad
-- left, not inner: a few rows carry a marking_period_id that does not resolve,
-- and they must not drop. schoolid is null on those, so the code join below
-- yields null labels for them too.
left join
    {{ ref("stg_focus__marking_periods") }} as mkp
    on ad.marking_period_id = mkp.marking_period_id
-- daily_code holds a short_name, NOT an id — unlike attendance_period, whose
-- codes are ids. short_name is unique only within a school and year, so both
-- scope the join.
left join
    {{ ref("stg_focus__attendance_codes") }} as ac
    on ad.syear = ac.syear
    and mkp.school_id = ac.school_id
    and ad.daily_code = ac.short_name
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select int_focus__attendance_day`

Expected: PASS, including `unique` and `not_null` on
`student_attendance_day_id`. A `unique` failure means a join fanned out — the
most likely cause is a duplicate `(syear, school_id, short_name)` in
`attendance_codes`.

- [ ] **Step 5: Confirm the code join actually resolved**

A wrong match key returns all-null labels and still builds and lints clean, so
check values, not just the build.

Run:

```bash
uv run dbt show --project-dir <worktree>/src/dbt/focus --inline "select countif(daily_code is not null) as coded, countif(daily_code is not null and daily_code_title is null) as unresolved from {{ ref('int_focus__attendance_day') }}"
```

Expected: `unresolved` is 0 and `coded` is greater than 0.

- [ ] **Step 6: Lint and commit**

```bash
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/intermediate/int_focus__attendance_day.sql src/dbt/focus/models/intermediate/properties/int_focus__attendance_day.yml </dev/null
git -C <worktree> add src/dbt/focus/models/intermediate/int_focus__attendance_day.sql src/dbt/focus/models/intermediate/properties/int_focus__attendance_day.yml
git -C <worktree> commit -m "feat(dbt): add int_focus__attendance_day

Resolves the daily attendance code to its title and excused/tardy flags. The
code column holds an attendance_codes short_name rather than an id, and codes
are scoped per school per year, so school is resolved from the marking period
first.

Refs #4865"
```

---

## Task 3: `int_focus__attendance_period`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__attendance_period.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__attendance_period.yml`

**Interfaces:**

- Consumes: `stg_focus__attendance_period`, `stg_focus__marking_periods`,
  `stg_focus__attendance_codes`.
- Produces: PK `student_attendance_period_id`. Grain is one row per student per
  school date per course period. Exposes `course_period_id` for consumers to
  join `int_focus__schedule`.

Note `stg_focus__attendance_period` has **no `syear` column** — `academic_year`
comes from the marking period.

- [ ] **Step 1: Write the properties file with the grain test**

Create `properties/int_focus__attendance_period.yml`:

```yaml
models:
  - name: int_focus__attendance_period
    description: >-
      Focus class-period attendance with both attendance codes resolved to their
      titles and excused/tardy flags — one row per student per school date per
      course period, the same grain as stg_focus__attendance_period. Both code
      columns are attendance_codes ids here, unlike attendance_day where the
      daily code is a short_name. Deliberately does not join course_periods or
      courses: int_focus__schedule already resolves those from course_period_id,
      and duplicating that resolution would mean two models to change when it
      changes. Internal-only — a rpt_ view must sit between this model and any
      external consumer.
    columns:
      - name: student_attendance_period_id
        description: >-
          Primary key — Focus attendance_period id; one row per student per
          school date per course period.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: academic_year
        description: >-
          Focus school year start year, resolved from the marking period because
          attendance_period carries no syear of its own.
      - name: schoolid
        description: >-
          Focus school id, resolved from the marking period. Null on rows whose
          marking_period_id does not resolve.
      - name: student_id
        description: >-
          Focus student id. Note this is the network student number prefixed
          with `8400` (Miami-Dade's FLDOE district number), not the bare student
          number.
        config:
          meta:
            contains_pii: true
      - name: school_date
        description: Calendar date the attendance was recorded for.
      - name: period_id
        description: Focus school period id the attendance was taken in.
      - name: course_period_id
        description: >-
          Focus course period (section) the attendance was taken in. Join
          int_focus__schedule on this to reach course, teacher and room.
      - name: marking_period_id
        description: Focus marking-period id the school date falls in.
      - name: attendance_code
        description: >-
          Official attendance_codes id recorded for the period — the code of
          record after any office correction.
      - name: attendance_teacher_code
        description: >-
          attendance_codes id the teacher originally entered. Differs from
          attendance_code where the office amended the record, and is null where
          the teacher did not take attendance.
      - name: attendance_reason
        description: Reason code recorded alongside the attendance.
      - name: hourly_attendance
        description: Whether the period is tracked as hourly attendance.
      - name: hours
        description: Hours credited for the period.
      - name: minutes_present
        description: Minutes the student was present for the period.
      - name: minutes_absent
        description: Minutes the student was absent for the period.
      - name: breaks
        description: Number of breaks recorded during the period.
      - name: break_minutes
        description: Total break minutes recorded during the period.
      - name: break_times
        description: Break start and end times recorded during the period.
      - name: break_out_time
        description: Time the student left for a break.
      - name: admin
        description: Whether the row was entered administratively.
      - name: admin_user_id
        description: Focus user id of the administrator who recorded the row.
      - name: mass_assigned
        description: Whether the code was applied by a mass-assignment action.
      - name: notified
        description: Whether a notification was sent for the row.
      - name: notified_callouts
        description: Callout notifications sent for the row.
      - name: last_updated_user
        description: Identifier of the user who last updated the row.
      - name: last_updated_date
        description: Source last-updated timestamp.
      - name: imported
        description: Y/N — whether the attendance row was imported.
      - name: attendance_code_title
        description: >-
          Readable name of the official attendance code (Present, Tardy, Absent
          Unexcused, Absent Excused, Absent Documented).
      - name: attendance_code_short_name
        description: Abbreviated official attendance code (P, T, U, AE, AD).
      - name: attendance_code_type
        description: >-
          Whether the official code is teacher-entered or official
          (office-entered).
      - name: attendance_code_state_code
        description: State-reported attendance code — P present, A absent.
      - name: attendance_code_excused
        description: Y when the official code marks the absence excused.
      - name: attendance_code_tardy
        description: Y when the official code represents a tardy.
      - name: attendance_code_state_attendance_type
        description: State attendance type the official code reports under.
      - name: attendance_teacher_code_title
        description: Readable name of the code the teacher originally entered.
      - name: attendance_teacher_code_short_name
        description: Abbreviated teacher-entered attendance code.
      - name: attendance_teacher_code_state_code
        description: State-reported code for the teacher-entered code.
      - name: attendance_teacher_code_excused
        description: Y when the teacher-entered code marks the absence excused.
      - name: attendance_teacher_code_tardy
        description: Y when the teacher-entered code represents a tardy.
      - name: marking_period_title
        description: Marking-period name from stg_focus__marking_periods.
      - name: marking_period_short_name
        description: Abbreviated marking-period name.
      - name: marking_period_type
        description: >-
          Marking-period granularity (year, semester, quarter, progress period).
      - name: marking_period_start_date
        description: First date of the marking period.
      - name: marking_period_end_date
        description: Last date of the marking period.
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select int_focus__attendance_period`

Expected: FAIL — model file does not exist.

- [ ] **Step 3: Write the model**

Create `int_focus__attendance_period.sql`:

```sql
select
    ap.id as student_attendance_period_id,
    ap.student_id,
    ap.school_date,
    ap.period_id,
    ap.course_period_id,
    ap.marking_period_id,
    ap.attendance_code,
    ap.attendance_teacher_code,
    ap.attendance_reason,
    ap.hourly_attendance,
    ap.hours,
    ap.minutes_present,
    ap.minutes_absent,
    ap.breaks,
    ap.break_minutes,
    ap.break_times,
    ap.break_out_time,
    ap.admin,
    ap.admin_user_id,
    ap.mass_assigned,
    ap.notified,
    ap.notified_callouts,
    ap.last_updated_user,
    ap.last_updated_date,
    ap.imported,

    -- attendance_period has no syear of its own; the marking period supplies
    -- both the year and the school
    mkp.syear as academic_year,
    mkp.school_id as schoolid,
    mkp.title as marking_period_title,
    mkp.short_name as marking_period_short_name,
    mkp.type as marking_period_type,
    mkp.start_date as marking_period_start_date,
    mkp.end_date as marking_period_end_date,

    ac.title as attendance_code_title,
    ac.short_name as attendance_code_short_name,
    ac.type as attendance_code_type,
    ac.state_code as attendance_code_state_code,
    ac.excused as attendance_code_excused,
    ac.tardy as attendance_code_tardy,
    ac.state_attendance_type as attendance_code_state_attendance_type,

    atc.title as attendance_teacher_code_title,
    atc.short_name as attendance_teacher_code_short_name,
    atc.state_code as attendance_teacher_code_state_code,
    atc.excused as attendance_teacher_code_excused,
    atc.tardy as attendance_teacher_code_tardy,

from {{ ref("stg_focus__attendance_period") }} as ap
left join
    {{ ref("stg_focus__marking_periods") }} as mkp
    on ap.marking_period_id = mkp.marking_period_id
-- both code columns are attendance_codes ids here, so no school/year scoping is
-- needed — unlike attendance_day, whose daily_code is a short_name
left join
    {{ ref("stg_focus__attendance_codes") }} as ac on ap.attendance_code = ac.id
left join
    {{ ref("stg_focus__attendance_codes") }} as atc
    on ap.attendance_teacher_code = atc.id
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select int_focus__attendance_period`

Expected: PASS, including `unique` and `not_null` on
`student_attendance_period_id`.

- [ ] **Step 5: Confirm both code joins resolved**

Run:

```bash
uv run dbt show --project-dir <worktree>/src/dbt/focus --inline "select countif(attendance_code is not null and attendance_code_title is null) as unresolved_official, countif(attendance_teacher_code is not null and attendance_teacher_code_title is null) as unresolved_teacher from {{ ref('int_focus__attendance_period') }}"
```

Expected: both counts are 0.

- [ ] **Step 6: Lint and commit**

```bash
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/intermediate/int_focus__attendance_period.sql src/dbt/focus/models/intermediate/properties/int_focus__attendance_period.yml </dev/null
git -C <worktree> add src/dbt/focus/models/intermediate/int_focus__attendance_period.sql src/dbt/focus/models/intermediate/properties/int_focus__attendance_period.yml
git -C <worktree> commit -m "feat(dbt): add int_focus__attendance_period

Resolves both the official and teacher-entered attendance codes. Does not join
course_periods — int_focus__schedule already resolves those from
course_period_id.

Refs #4865"
```

---

## Task 4: Load the link tables and verify their grain

**This task is a gate, not a code change.** It requires pushing Task 1 through
Task 3, waiting for the Dagster branch deployment, and launching a run.
Coordinator action — do not dispatch to a subagent.

**Files:** none.

**Interfaces:**

- Consumes: Task 1's config.
- Produces: rows in the two BigQuery tables, plus a verified answer to whether
  `(assignment_type_id, course_period_id, marking_period_id)` is unique — which
  Task 7's weight join depends on.

- [ ] **Step 1: Push the branch**

```bash
git -C <worktree> push -u origin cbini/feat/claude-focus-intermediates
```

The `focus.yaml` path is in the trigger list for
`.github/workflows/deploy-prod-kippmiami.yaml`, which fires on `pull_request`,
so opening the PR builds a branch deployment. Open the PR now using
`.github/pull_request_template.md` as the body, with `Refs #4865`.

- [ ] **Step 2: Wait for the branch deployment to finish**

`dagster-cloud-deploy / deploy` emits one same-named check-run per code location
(about five). Wait for ALL of them to reach a terminal conclusion before
launching anything — a shared-library change redeploys every consuming location.

Run: `gh pr checks <pr-number> --json name,bucket,state`

- [ ] **Step 3: Launch the two new dlt assets in the branch deployment**

Discover the branch deployment name with `mcp__dagster__list_deployments`, then
preview with `confirm=False` before executing:

```text
mcp__dagster__launch_run(
    deployment="<branch-deployment-name>",
    asset_keys=[
        ["kippmiami", "dlt", "focus", "gradebook_assignments_join_course_periods"],
        ["kippmiami", "dlt", "focus", "gradebook_assignment_types_join_course_periods"],
    ],
    confirm=False,
)
```

Show the preview to the user before re-running with `confirm=True`. The
`@dlt_assets` op runs over a source narrowed to the run's asset selection, so
only these two tables load, not all 78.

- [ ] **Step 4: Confirm both tables landed**

The destination dataset has no deployment segment, so a branch-deployment load
writes to the same dataset prod uses.

```sql
select
  (select count(*) from `teamster-332318.dagster_kippmiami_dlt_focus.gradebook_assignments_join_course_periods`) as assignment_link_rows,
  (select count(*) from `teamster-332318.dagster_kippmiami_dlt_focus.gradebook_assignment_types_join_course_periods`) as type_link_rows
```

Expected: both well above zero. Use `count(*)`, never `__TABLES__.row_count`,
which lags and can read 0 for a populated table.

- [ ] **Step 5: Verify the type-link triple is unique**

This is the one assumption in the design that was never measured, because the
table was not in BigQuery when the design was written.

```sql
select count(*) as duplicate_triples
from (
  select assignment_type_id, course_period_id, marking_period_id
  from `teamster-332318.dagster_kippmiami_dlt_focus.gradebook_assignment_types_join_course_periods`
  group by 1, 2, 3
  having count(*) > 1
)
```

Expected: 0. **If this returns non-zero, stop and report it** — Task 7's weight
join needs a documented tie-break rule rather than the triple, and that is a
design decision, not an implementation detail.

- [ ] **Step 6: Profile which columns carry data**

Staging models project only columns that carry data. Run this for each of the
two tables, substituting the table name:

```sql
with rows_json as (
  select to_json(t) as j
  from `teamster-332318.dagster_kippmiami_dlt_focus.gradebook_assignments_join_course_periods` as t
)
select k, countif(to_json_string(j[k]) not in ('null', '""')) as populated
from rows_json, unnest(json_keys(j, 1)) as k
group by k
order by populated desc
```

Record which columns come back with `populated = 0`. Tasks 5 and 6 drop those
from their projections and their contracts.

---

## Task 5: `stg_focus__gradebook_assignments_join_course_periods`

**Files:**

- Create:
  `src/dbt/focus/models/staging/stg_focus__gradebook_assignments_join_course_periods.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml`

**Interfaces:**

- Consumes: `source("focus", "gradebook_assignments_join_course_periods")`.
- Produces: PK `id`. Supplies `assignment_id`, `course_period_id`,
  `marking_period_id`, `assigned_date`, `due_date`, `publish_date` to Task 7.

- [ ] **Step 1: Write the model**

Create the `.sql` file. Start from this projection and **remove any column Task
4 Step 6 reported as `populated = 0`**:

```sql
select
    id,
    assignment_id,
    course_period_id,
    marking_period_id,
    marking_period_short_name,
    assigned_date,
    due_date,
    publish_date,
    show_assigned_time,
    show_due_time,
    show_publish_time,
    assigned_to_all_students,
    include_weekends,
    course_buffer,
    restrict_test_to_times,
    restrict_test_start_time,
    restrict_test_end_time,
    google_classroom_url,
    external_api_id,
    external_api_uuid,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_assignments_join_course_periods") }}
```

The audit quad (`created_by_class`, `created_by_id`, `updated_by_class`,
`updated_by_id`) and `_dlt_*` are dropped per convention. There is no `deleted`
column, so no soft-delete filter.

- [ ] **Step 2: Write the properties file**

Create the `.yml`. Every projected column needs a `data_type` — the model is
contract-enforced. Postgres-to-BigQuery type mapping for this table: `bigint` to
`int`, `character varying` to `string`, `timestamp with time zone` to
`timestamp`, `boolean` to `boolean`, `time without time zone` to `time`. Keep
the column order identical to the `.sql`, and drop the same columns you dropped
there.

```yaml
models:
  - name: stg_focus__gradebook_assignments_join_course_periods
    description: >-
      Focus link between a gradebook assignment and the course periods it was
      assigned to — one row per assignment per course period, carrying the
      assignment's dates for that section. An assignment is commonly assigned to
      several sections, so this table is many-to-one against
      stg_focus__gradebook_assignments.
    columns:
      - name: id
        description: Primary key — Focus assignment/course-period link id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: assignment_id
        description: >-
          Focus gradebook assignment being linked (joins
          `stg_focus__gradebook_assignments`).
        data_type: int
        data_tests:
          - not_null:
              config:
                severity: error
          - relationships:
              arguments:
                to: ref('stg_focus__gradebook_assignments')
                field: assignment_id
              config:
                severity: error
      - name: course_period_id
        description: >-
          Focus course period (section) the assignment was assigned to.
        data_type: int
      - name: marking_period_id
        description: Focus marking period the assignment belongs to.
        data_type: int
      - name: marking_period_short_name
        description: >-
          Abbreviated marking-period name denormalized onto the link row.
        data_type: string
      - name: assigned_date
        description: Date the assignment was assigned to this section.
        data_type: timestamp
      - name: due_date
        description: Date the assignment is due for this section.
        data_type: timestamp
      - name: publish_date
        description: Date the assignment became visible for this section.
        data_type: timestamp
      - name: show_assigned_time
        description: Whether the assigned time is shown alongside the date.
        data_type: boolean
      - name: show_due_time
        description: Whether the due time is shown alongside the date.
        data_type: boolean
      - name: show_publish_time
        description: Whether the publish time is shown alongside the date.
        data_type: boolean
      - name: assigned_to_all_students
        description: >-
          Whether every student in the section received the assignment, as
          opposed to a selected subset.
        data_type: boolean
      - name: include_weekends
        description: Whether weekends count toward the assignment's date span.
        data_type: boolean
      - name: course_buffer
        description: Whether a course buffer applies to the assignment dates.
        data_type: boolean
      - name: restrict_test_to_times
        description:
          Whether the assignment is a test restricted to a time window.
        data_type: boolean
      - name: restrict_test_start_time
        description: Start of the permitted testing window.
        data_type: time
      - name: restrict_test_end_time
        description: End of the permitted testing window.
        data_type: time
      - name: google_classroom_url
        description: Google Classroom link for the assignment, where integrated.
        data_type: string
      - name: external_api_id
        description: >-
          External API id for the link, when it arrived from an integrated
          grading tool.
        data_type: int
      - name: external_api_uuid
        description: External API uuid for the link.
        data_type: string
      - name: imported
        description: Y/N — whether the link row was imported.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify the contract and PK hold**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select stg_focus__gradebook_assignments_join_course_periods`

Expected: PASS. A contract error naming a column means the `data_type` does not
match what dlt landed — fix the YAML to match BigQuery, not the other way
around.

- [ ] **Step 4: Lint and commit**

```bash
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/staging/stg_focus__gradebook_assignments_join_course_periods.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml </dev/null
git -C <worktree> add src/dbt/focus/models/staging/stg_focus__gradebook_assignments_join_course_periods.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml
git -C <worktree> commit -m "feat(dbt): add stg_focus__gradebook_assignments_join_course_periods

Refs #4865"
```

---

## Task 6: `stg_focus__gradebook_assignment_types_join_course_periods`

**Files:**

- Create:
  `src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types_join_course_periods.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types_join_course_periods.yml`

**Interfaces:**

- Consumes: `source("focus", "gradebook_assignment_types_join_course_periods")`.
- Produces: PK `id`. Supplies `assignment_type_id`, `course_period_id`,
  `marking_period_id`, `final_grade_percent`, `drop_lowest_grades` to Task 7.

- [ ] **Step 1: Write the model**

Create the `.sql` file. Start from this projection and **remove any column Task
4 Step 6 reported as `populated = 0`**:

```sql
select
    id,
    assignment_type_id,
    course_period_id,
    marking_period_id,
    template_id,
    template_category_id,
    final_grade_percent,
    drop_lowest_grades,
    color,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_assignment_types_join_course_periods") }}
```

- [ ] **Step 2: Write the properties file**

```yaml
models:
  - name: stg_focus__gradebook_assignment_types_join_course_periods
    description: >-
      Focus link between a gradebook assignment category and the course periods
      it applies to, carrying that category's weight toward the section's final
      grade. One row per category per course period per marking period —
      category weights change by marking period, so the marking period is part
      of the grain.
    columns:
      - name: id
        description: Primary key — Focus category/course-period link id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: assignment_type_id
        description: >-
          Focus gradebook assignment category being linked (joins
          `stg_focus__gradebook_assignment_types`).
        data_type: int
        data_tests:
          - not_null:
              config:
                severity: error
          - relationships:
              arguments:
                to: ref('stg_focus__gradebook_assignment_types')
                field: assignment_type_id
              config:
                severity: error
      - name: course_period_id
        description: Focus course period (section) the category applies to.
        data_type: int
      - name: marking_period_id
        description: >-
          Focus marking period the weighting applies to. Part of the grain — the
          same category and section repeat across marking periods with different
          weights.
        data_type: int
      - name: template_id
        description: Gradebook template the category came from, where templated.
        data_type: int
      - name: template_category_id
        description: Template category the category came from, where templated.
        data_type: int
      - name: final_grade_percent
        description: >-
          Percentage this category contributes to the section's final grade for
          the marking period. Populated on nearly every row.
        data_type: numeric
      - name: drop_lowest_grades
        description: >-
          Number of lowest scores dropped from the category before averaging.
        data_type: numeric
      - name: color
        description: Display color assigned to the category in the gradebook.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select stg_focus__gradebook_assignment_types_join_course_periods`

Expected: PASS.

- [ ] **Step 4: Lint and commit**

```bash
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types_join_course_periods.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types_join_course_periods.yml </dev/null
git -C <worktree> add src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types_join_course_periods.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types_join_course_periods.yml
git -C <worktree> commit -m "feat(dbt): add stg_focus__gradebook_assignment_types_join_course_periods

Carries each gradebook category's weight toward the section's final grade.
Marking period is part of the grain — weights change by marking period.

Refs #4865"
```

---

## Task 7: `int_focus__gradebook_grades`

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__gradebook_grades.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml`

**Interfaces:**

- Consumes: `stg_focus__gradebook_grades`, `stg_focus__gradebook_assignments`,
  `stg_focus__gradebook_assignment_types`, `stg_focus__schedule`, and both
  staging models from Tasks 5 and 6.
- Produces: PK `student_gradebook_grade_id`. Grain is one row per grade.

The hard part is that an assignment maps to many course periods while a grade
names only the student and the assignment. The student's schedule picks the
right one.

- [ ] **Step 1: Write the properties file with the grain test**

Create `properties/int_focus__gradebook_grades.yml`:

```yaml
models:
  - name: int_focus__gradebook_grades
    description: >-
      Focus gradebook scores with the assignment, its category and category
      weight, and the course period the score belongs to — one row per score,
      the same grain as stg_focus__gradebook_grades. A gradebook grade names
      only the student and the assignment, and an assignment is commonly
      assigned to several sections, so the course period is resolved by keeping
      the one the student is scheduled into. Scores whose assignment has no
      course-period link keep their points and carry a null course period rather
      than dropping. Internal-only — a rpt_ view must sit between this model and
      any external consumer.
    columns:
      - name: student_gradebook_grade_id
        description: >-
          Primary key — Focus gradebook_grades id; one row per student per
          assignment.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: student_id
        description: >-
          Focus student id. Note this is the network student number prefixed
          with `8400` (Miami-Dade's FLDOE district number), not the bare student
          number.
        config:
          meta:
            contains_pii: true
      - name: assignment_id
        description: Focus gradebook assignment the score is for.
      - name: standard_id
        description: >-
          Focus standard the score is against, for standards-based rows.
      - name: points
        description: Points the student earned on the assignment.
      - name: possible_points
        description: >-
          Points possible for this student, when it differs from the
          assignment's own point value (e.g. an accommodation).
      - name: letter_grade
        description: >-
          Letter grade recorded for the score, for assignments graded by letter
          rather than points.
      - name: exclude_from_average
        description: Whether this score is excluded from the gradebook average.
      - name: late
        description: Whether the assignment was turned in late.
      - name: highlight
        description: Y/N — whether the teacher flagged the score for follow-up.
      - name: comment
        description: Free-text teacher comment on the score.
        config:
          meta:
            contains_pii: true
      - name: comment_codes
        description: Canned comment codes attached to the score.
      - name: accommodations
        description: Accommodations applied when the assignment was scored.
      - name: last_updated_user
        description: Identifier of the user who last updated the score.
      - name: last_updated_date
        description: Source last-updated timestamp.
      - name: course_period_id
        description: >-
          Course period the score belongs to, resolved by intersecting the
          assignment's course periods with the ones the student is scheduled
          into. Null where the assignment has no course-period link row.
      - name: marking_period_id
        description: >-
          Marking period the assignment belongs to for that course period. Null
          alongside a null course_period_id.
      - name: assigned_date
        description: Date the assignment was assigned to the student's section.
      - name: due_date
        description: Date the assignment was due for the student's section.
      - name: publish_date
        description: >-
          Date the assignment became visible to the student's section.
      - name: assignment_type_id
        description: Focus gradebook category the assignment belongs to.
      - name: assignment_title
        description: Assignment name as the teacher entered it.
      - name: assignment_points
        description: >-
          Points the assignment is worth by default, before any per-student
          override in possible_points.
      - name: assignment_description
        description: Free-text assignment description.
      - name: assignment_exclude_from_average
        description: >-
          Whether the assignment as a whole is excluded from the gradebook
          average, independent of the per-score exclude_from_average flag.
      - name: assignment_type_title
        description: >-
          Gradebook category name (Formative, Homework, Work Habits and so on).
      - name: assignment_type_final_grade_percent
        description: >-
          Percentage the category contributes to the section's final grade for
          this marking period. Null where the course period did not resolve.
      - name: assignment_type_drop_lowest_grades
        description: >-
          Number of lowest scores dropped from the category before averaging.
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select int_focus__gradebook_grades`

Expected: FAIL — model file does not exist.

- [ ] **Step 3: Write the model**

Create `int_focus__gradebook_grades.sql`:

```sql
with
    -- group by, not a join: schedule repeats a student/course-period pair on
    -- ~299 combinations, and joining it as a table would double those grades.
    -- Collapsing to the pair states the grain this lookup is meant to have.
    student_course_periods as (
        select student_id, course_period_id,
        from {{ ref("stg_focus__schedule") }}
        group by student_id, course_period_id
    ),

    -- An assignment is assigned to many sections, so the link alone fans a
    -- grade out. Intersecting with the student's own sections picks exactly
    -- one. Inner joins here are deliberate: this CTE holds only grades whose
    -- course period resolved, and it is LEFT joined back on below so the rest
    -- survive.
    grade_course_periods as (
        select
            gg.id as student_gradebook_grade_id,
            ajcp.course_period_id,
            ajcp.marking_period_id,
            ajcp.assigned_date,
            ajcp.due_date,
            ajcp.publish_date,
        from {{ ref("stg_focus__gradebook_grades") }} as gg
        inner join
            {{ ref("stg_focus__gradebook_assignments_join_course_periods") }}
            as ajcp
            on gg.assignment_id = ajcp.assignment_id
        inner join
            student_course_periods as scp
            on gg.student_id = scp.student_id
            and ajcp.course_period_id = scp.course_period_id
    )

select
    gg.id as student_gradebook_grade_id,
    gg.student_id,
    gg.assignment_id,
    gg.standard_id,
    gg.points,
    gg.possible_points,
    gg.letter_grade,
    gg.exclude_from_average,
    gg.late,
    gg.highlight,
    gg.comment,
    gg.comment_codes,
    gg.accommodations,
    gg.last_updated_user,
    gg.last_updated_date,

    gcp.course_period_id,
    gcp.marking_period_id,
    gcp.assigned_date,
    gcp.due_date,
    gcp.publish_date,

    ga.assignment_type_id,
    ga.title as assignment_title,
    ga.points as assignment_points,
    ga.description as assignment_description,
    ga.exclude_from_average as assignment_exclude_from_average,

    gat.title as assignment_type_title,

    atjcp.final_grade_percent as assignment_type_final_grade_percent,
    atjcp.drop_lowest_grades as assignment_type_drop_lowest_grades,

from {{ ref("stg_focus__gradebook_grades") }} as gg
left join
    grade_course_periods as gcp
    on gg.id = gcp.student_gradebook_grade_id
left join
    {{ ref("stg_focus__gradebook_assignments") }} as ga
    on gg.assignment_id = ga.assignment_id
left join
    {{ ref("stg_focus__gradebook_assignment_types") }} as gat
    on ga.assignment_type_id = gat.assignment_type_id
-- the triple, not the pair: the same category and section repeat across marking
-- periods with different weights
left join
    {{ ref("stg_focus__gradebook_assignment_types_join_course_periods") }}
    as atjcp
    on ga.assignment_type_id = atjcp.assignment_type_id
    and gcp.course_period_id = atjcp.course_period_id
    and gcp.marking_period_id = atjcp.marking_period_id
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
`uv run dbt build --project-dir <worktree>/src/dbt/focus --select int_focus__gradebook_grades`

Expected: PASS. A `unique` failure on `student_gradebook_grade_id` means one of
the joins fanned out — check the type-link triple first, then whether
`grade_course_periods` returned more than one row for some grade.

- [ ] **Step 5: Confirm no grades were lost and the resolution worked**

```bash
uv run dbt show --project-dir <worktree>/src/dbt/focus --inline "select (select count(*) from {{ ref('stg_focus__gradebook_grades') }}) as staging_rows, count(*) as model_rows, countif(course_period_id is null) as unresolved_course_period, countif(assignment_type_final_grade_percent is not null) as with_weight from {{ ref('int_focus__gradebook_grades') }}"
```

Expected: `model_rows` equals `staging_rows` exactly — no grades gained or lost.
`unresolved_course_period` is small (about 30 at the time of design) and matches
the count of grades whose assignment has no link row. `with_weight` is greater
than 0.

- [ ] **Step 6: Lint and commit**

```bash
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/intermediate/int_focus__gradebook_grades.sql src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml </dev/null
git -C <worktree> add src/dbt/focus/models/intermediate/int_focus__gradebook_grades.sql src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml
git -C <worktree> commit -m "feat(dbt): add int_focus__gradebook_grades

Resolves each score's course period by intersecting the assignment's sections
with the ones the student is scheduled into — an assignment is commonly
assigned to several sections, so the link table alone fans a grade out. Carries
the category weight, keyed on category, course period and marking period.

Refs #4865"
```

---

## Task 8: Update issue #4865 and finish the PR

**Files:** none.

- [ ] **Step 1: Rewrite the issue body**

#4865 currently states that all three models need no new ingestion and that
staging coverage is the only gate. True for the two attendance models, wrong for
the gradebook model. Rewrite the Outstanding and Depends-on sections to record
the ingestion dependency and the `short_name` versus `id` split on the
attendance code columns. Use `mcp__github__issue_write`.

`issue_write` strips `<...>` tokens even inside backticks and entity-encodes `&`
and `"`. Read the stored body back with
`gh api repos/TEAMSchools/teamster/issues/4865 --jq .body` and verify it matches
intent.

- [ ] **Step 2: Push and confirm CI is green on both surfaces**

```bash
git -C <worktree> push
```

dbt Cloud is a commit _status_; Trunk, CodeQL and `claude` are _check runs_.
Check both before calling the PR green:

```bash
gh pr checks <pr-number> --json name,bucket,state
gh api repos/TEAMSchools/teamster/commits/<sha>/status
```

- [ ] **Step 3: Fetch dbt Cloud CI warnings**

```text
mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)
```

Warnings unchanged from `main` are pre-existing — search for an existing tracker
issue before filing anything.

- [ ] **Step 4: Process the `claude-review` findings**

Invoke `superpowers:receiving-code-review` BEFORE acting on any finding. Verify
each claim, including its file and line citations, against the code — the bot
asserts repo conventions that are not always enforced. Post a per-finding
verdict as a PR comment, declines included with reasons. A silent fix reads to a
human reviewer as an unaddressed review.

---

## Notes for the implementer

**The 2016 and 2010 historical rows are why some joins look over-scoped.**
`attendance_codes` has one duplicate `(syear, school_id, short_name)` in syear
2010, and `attendance_calendar` has 177 duplicate default-calendar keys in
syear 2016. Neither touches AY2026-27 data, which is all `attendance_day` and
`attendance_period` carry. The `unique` test on each model's PK is what would
catch it if that ever changed.

**Do not add an `attendance_calendar` join to either attendance model.** The
design rejects it on evidence: `minutes` is `999` on every matched 2026 row, and
detecting missing attendance records needs a scaffold at a different grain. The
spec records how to scope the join correctly if a future consumer genuinely
needs it.

**Do not create `__pivot` models.** None of the three source tables has a
`custom_*` column.
