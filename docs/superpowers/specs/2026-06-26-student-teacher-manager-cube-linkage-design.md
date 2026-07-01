# Link Student-Data Domains to Responsible Teacher — Cube Design

**Date:** 2026-06-26 (revised 2026-07-01) **Status:** Active **Branch:**
`cristinabaldor/feat/claude-student-teacher-manager-cube-linkage` **Issue:**
[#4273](https://github.com/TEAMSchools/teamster/issues/4273)

## Context

Analysts need to slice student-data views by the **responsible teacher**
(point-in-time):

- **Attendance** → the student's **homeroom/advisory** teacher.
- **Assessments** → the **subject-area section lead** for each kid.
- Later (out of scope here, but the primitive is reused): gradebooks and other
  section-scoped student data.

The teacher's **manager and reporting chain** (direct manager, AP, School
Leader) are **deferred** — see [Deferred](#deferred-blocked-on-4269) below.

Design choices:

- Attendance uses the **homeroom** (an `HR`-credit section) teacher.
- Defines "responsible teacher" as **`role = 'Lead Teacher'`** in
  `bridge_course_section_teachers` — verified unique per section in 97.8% of
  sections; the ~2% with multiple leads are mid-year handoffs resolved by
  point-in-time date overlap.
- Resolves the teacher to a **single value per enrollment in dbt**, so the
  fact-to-teacher path is `many_to_one` and **adds zero fan-out** to
  attendance/assessment measures.

Confirmed decisions: both domains in one spec; Lead Teacher only; teacher only
this PR (manager/chain deferred).

## Why the resolution must live in dbt, not a Cube join

The obvious question is whether Cube can just join the fact to
`bridge_course_section_teachers` and skip new dbt work. Cube _can_ host
multi-table joins inline — `staff_work_history.yml` does a 7-table SCD2
period-intersection in inline `sql:`. The blocker is narrower:

- **Uniqueness must be _enforced_, and only dbt can do that.** Resolving the
  responsible teacher requires filtering to `Lead Teacher`, overlapping dates,
  then **deduplicating** the ~2% of sections with overlapping leads to one row.
  Cube has no window functions and no dedup, and its `many_to_one` fan-trap
  protection **trusts the declared relationship** rather than verifying it — a
  Cube-only join that is not perfectly 1:1 silently double-counts attendance
  days and assessment scores. dbt is where the value is deduped **and** pinned
  with a `unique` test. That test is the entire safety guarantee.
- **Assessments carry no query date to anchor a point-in-time join.** A score is
  keyed at section-enrollment grain with no date, so "which lead teacher, given
  overlapping windows" cannot be resolved at query time (unlike
  `staff_work_history`, whose queries always carry a date for the `BETWEEN`).
- **Attendance carries no section key at all.** The fact is keyed on
  `student_enrollment_key`; "homeroom teacher" is a derived path (enrollment →
  `HR`-credit section → lead teacher) that does not exist as joinable keys.

The resolution therefore lives in dbt. But it does **not** need new `dim_`
models or new cubes — it is columns on the two enrollment dims that already back
the cubes wired into these views (below).

## Confirmed facts (from data and code exploration)

- `bridge_course_section_teachers` (`kipptaf_marts`): grain section x teacher x
  period; cols `course_section_key`, `staff_key`, `role`,
  `effective_start_date`, `effective_end_date`. `role` values: `Lead Teacher`,
  `Co-teacher`, `Gradebook Access (edit)`, `Blended Learning`,
  `Job Share Teacher`, `PhysEd Share`.
- `dim_student_section_enrollments` (grain `student_section_enrollment_key`):
  FKs `student_enrollment_key`, `course_section_key`; `entry_date`, `exit_date`,
  `is_dropped_section`. `dim_courses.credit_type = 'HR'` marks homeroom courses.
  Already read by the `student_section_enrollments` cube.
- `dim_student_enrollments` (grain `student_enrollment_key`): the school-stint
  dim. Already read by the `student_school_enrollments` cube.
- `fct_assessment_scores_enrollment_scoped`: FK `student_section_enrollment_key`
  (already subject-resolved) plus `enrollment_resolution` value
  `subject_section` or `homeroom`. Its cube already joins `many_to_one` to
  `student_section_enrollments`.
- `fct_student_attendance_daily`: daily grain, FK `student_enrollment_key`
  (school stint, **no section key**). Its cubes already join `many_to_one` to
  `student_school_enrollments`. A SNAPSHOT cube.
- Homeroom is **not** a standalone table today. The homeroom section is the
  student's `HR`-credit section enrollment; its Lead Teacher is the homeroom
  teacher. (`int_powerschool__advisory` resolves it the older way, by
  `course_code LIKE 'HR%'`; we instead reuse the section primitive.)
- Cube conventions: cubes `public: false`, views public; derived grains / dedup
  / multi-table resolution live in dbt read via `sql_table`; student-domain
  cubes are named `student*` (drives `isStudentMember` gating).

## Design

Three layers. Everything reads tables already in `kipptaf_marts`. **No new dbt
models, no new cubes, no new fact-cube joins** — the fact-to-enrollment joins
already exist.

### 1. dbt — resolve one teacher per enrollment (point-in-time)

**`dim_student_section_enrollments`** — add resolved columns (grain unchanged:
one row per `student_section_enrollment_key`):

- LEFT JOIN `bridge_course_section_teachers` on `course_section_key`,
  `role = 'Lead Teacher'`, and a **half-open date overlap** of the bridge
  effective window with the section `entry_date`/`exit_date`
  (`src/dbt/CLAUDE.md` date-range-join rule: `start <= x and x < end`).
- Collapse the rare multi-lead case to one value with `dbt_utils.deduplicate`
  (partition by `student_section_enrollment_key`, order by
  `effective_start_date`) — **no** `qualify`/`distinct`.
- New columns: `lead_teacher_staff_key`, `teacher_role`. No effective-date
  columns — nothing shipping needs them, and the deferred manager approach may
  not use this anchor.
- Null-wrap `lead_teacher_staff_key` per the nullable-surrogate-key rule; add a
  `relationships` test `lead_teacher_staff_key -> dim_staff.staff_key`. The
  dim's existing PK `unique` test guarantees the added columns did not change
  the grain (the fan-out guard).

**`dim_student_enrollments`** — add `homeroom_teacher_staff_key` (grain
unchanged: one row per `student_enrollment_key`):

- Resolve the stint's `HR`-credit section, then its Lead Teacher, deduped to one
  value per `student_enrollment_key` (rare mid-year homeroom change → keep
  earliest). The heavier resolution SQL may live in a supporting `int_` model
  that this dim reads rather than inline — an implementation-plan detail.
- New column: `homeroom_teacher_staff_key`. `relationships` test to
  `dim_staff.staff_key`; existing PK `unique` test is the fan-out guard.

### 2. Cube — widen the two existing dim cubes

No new cubes. Each existing dim cube exposes the teacher FK and gains one
`many_to_one` join to `staff` for the teacher name.

- **`student_section_enrollments`** — add dims `lead_teacher_staff_key` (FK,
  degenerate) and `teacher_role`; add join `many_to_one` to `staff` on
  `lead_teacher_staff_key`. Prefix the join so members read `staff_full_name`
  etc.
- **`student_school_enrollments`** (reads `dim_student_enrollments`) — add dim
  `homeroom_teacher_staff_key`; add the same `many_to_one` join to `staff`.

The fact cubes (`student_attendance`, `student_assessment_scores`) are
**unchanged** — they already join to these enrollment cubes.

### 3. Cube — view edits

View `join_path` includes surface the teacher (prefix the `staff` join so
members read `staff_full_name`, etc.). New `Teacher` folder on each view.

- **`student_attendance_detail` / `student_assessment_scores_detail`**: teacher
  `staff_key`, `full_name`, `first_name`, `last_name`, plus `teacher_role`.
- **`student_attendance_summary` / `student_assessment_scores_summary`**: only
  non-PII groupers — teacher `staff_key` and `teacher_role`. Names excluded
  (summary carries no PII).

**Access policy**: teacher dimensions follow the same access rules as all other
student data for the school — they sit under the view's existing
`cube-access-student-data` scope; no separate staff-PII tier.

### Fan-out and measure safety (the key risk)

- Fact-to-teacher is `many_to_one` (one value per enrollment after dbt
  resolution) → **no fan-out**; `count_students` / `count_scores` /
  `avg_daily_attendance` unchanged whether or not the teacher dim is in the
  query.
- `student_attendance` is a SNAPSHOT cube (#4160). We add **dimensions only, no
  measures**, and the join is row-preserving, so the snapshot anchor injection
  is unaffected. Verify a snapshot measure (e.g.
  `count_chronically_absent_year_end`) grouped by teacher returns the same total
  as ungrouped.
- Assessments: the fact's `student_section_enrollment_key` already points at the
  subject section (or homeroom fallback per `enrollment_resolution`), so the
  section dim yields the subject teacher automatically; consumers can filter
  `enrollment_resolution = 'subject_section'` for strict subject matches.

## Files

| Action | Path                                                                                               |
| ------ | -------------------------------------------------------------------------------------------------- |
| Modify | `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql` plus its `.yml`      |
| Modify | `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql` plus its `.yml`              |
| Modify | `src/cube/model/cubes/students/student_section_enrollments.yml` (add dims plus `staff` join)       |
| Modify | `src/cube/model/cubes/students/student_school_enrollments.yml` (add dim plus `staff` join)         |
| Modify | `src/cube/model/views/student_attendance/student_attendance_detail.yml`, `..._summary.yml`         |
| Modify | `src/cube/model/views/student_assessments/student_assessment_scores_detail.yml`, `..._summary.yml` |

Possibly one new `int_` helper model feeding the homeroom resolution
(implementation-plan call). No `cube.js` change (existing student-prefixed cubes
keep their `isStudentMember` gating; no new SNAPSHOT cube).

## Implementation order

1. dbt: resolve `lead_teacher_staff_key` / `teacher_role` on
   `dim_student_section_enrollments`, then `homeroom_teacher_staff_key` on
   `dim_student_enrollments` (plus properties, tests).
   `uv run dbt build --select dim_student_section_enrollments dim_student_enrollments --project-dir src/dbt/kipptaf --target dev`.
2. Cube: widen `student_section_enrollments` and `student_school_enrollments`.
3. View edits plus folders.

## Verification

- **dbt**: build the two dims in dev; assert PK uniqueness still holds and the
  new `relationships` tests pass. Cross-check in BigQuery: one teacher per
  `student_section_enrollment_key`; homeroom teacher present for current-year
  enrollments; spot-check a known section's Lead Teacher.
- **Cube** (point cube `sql_table` at the dev `zz_<user>_kipptaf_marts` copies
  per `src/cube/CLAUDE.md`, revert before commit): `/sql` compiles the teacher
  members; `/load` returns the teacher for a sample student.
- **Measure safety**: via the cube MCP, confirm `count_students` (attendance)
  and `count_scores` (assessments) are **identical** grouped-by-teacher vs.
  ungrouped over the same filter; repeat for one snapshot measure.
- **Access**: confirm the teacher block is hidden without
  `cube-access-student-data`, exactly like the rest of the student data on the
  view.

## Deferred (blocked on #4269)

Manager and reporting-chain linkage — direct manager, plus AP
(`Assistant School Leader`) and School Leader tiers — is deferred until
[#4269](https://github.com/TEAMSchools/teamster/pull/4269) merges. That PR
introduces `dim_staff_reporting_chain` (the transitive org closure) and
`dim_staff_cube_access`. The point-in-time anchoring approach for the manager
join is **TBD** and will be decided when that model lands (we may take a
different route entirely). The teacher `staff_key` resolved here is the join
anchor; adding managers will not rework the teacher layer built in this spec.
