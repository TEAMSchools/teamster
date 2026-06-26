# Link Student-Data Domains to Responsible Teacher and Manager — Cube Design

**Date:** 2026-06-26 **Status:** Active **Branch:**
`cristinabaldor/feat/claude-student-teacher-manager-cube-linkage` **Issue:**
[#4273](https://github.com/TEAMSchools/teamster/issues/4273)

## Context

Analysts need to slice student-data views by the **responsible teacher** and
that teacher's **direct manager** (point-in-time):

- **Attendance** → the student's **homeroom/advisory** teacher.
- **Assessments** → the **subject-area section lead** for each kid.
- Later (out of scope here, but the primitive is reused): gradebooks and other
  section-scoped student data.

Design choices:

- Attendance uses the **homeroom** (an `HR`-credit section) teacher.
- Defines "responsible teacher" as **`role = 'Lead Teacher'`** in
  `bridge_course_section_teachers` — verified unique per section in 97.8% of
  sections; the ~2% with multiple leads are mid-year handoffs resolved by
  point-in-time date overlap.
- Resolves teacher to a **single row per enrollment** in dbt, so the
  fact-to-teacher join is `many_to_one` and **adds zero fan-out** to
  attendance/assessment measures.
- Reuses the existing point-in-time **direct-manager** cubes
  (`staff_reporting_relationships` + `staff_manager`). The reporting chain —
  needed to cover cases where the AP/School Leader is **not** the teacher's
  direct manager — is **deferred until after the `dim_staff_reporting_chain` PR
  merges**.

Confirmed decisions: both domains in one spec; Lead Teacher only; direct manager
only, point-in-time.

## Confirmed facts (from data and code exploration)

- `bridge_course_section_teachers` (kipptaf_marts): grain section x teacher x
  period; cols `course_section_key`, `staff_key`, `role`,
  `effective_start_date`, `effective_end_date`. `role` values: `Lead Teacher`,
  `Co-teacher`, `Gradebook Access (edit)`, `Blended Learning`,
  `Job Share Teacher`, `PhysEd Share`.
- `dim_student_section_enrollments`: PK `student_section_enrollment_key`; FKs
  `student_enrollment_key`, `course_section_key`; `entry_date`, `exit_date`,
  `is_dropped_section`. `dim_courses.credit_type = 'HR'` marks homeroom courses.
- `fct_assessment_scores_enrollment_scoped`: FK `student_section_enrollment_key`
  (already subject-resolved) plus `enrollment_resolution` value
  `subject_section` or `homeroom`.
- `fct_student_attendance_daily`: daily grain, FK `student_enrollment_key`
  (school stint, **no section key**). A SNAPSHOT cube.
- Homeroom is **not** in `kipptaf_marts` today. The homeroom section is just the
  student's `HR`-credit section enrollment; its Lead Teacher is the homeroom
  teacher. (`int_powerschool__advisory` resolves it the older way, by
  `course_code LIKE 'HR%'`; we instead reuse the section primitive.)
- Existing point-in-time manager pattern: `staff_reporting_relationships` (SCD2
  period-intersection, direct manager) plus `staff_manager` (role-alias of
  `staff`), folded by `staff_work_history`. Reuse verbatim.
- Cube conventions: cubes `public: false`, views public; transformation
  (multi-table joins, date overlap, derived grain) lives in dbt read via
  `sql_table`, not inline cube SQL; student-domain cubes must be named
  `student*` (drives `isStudentMember` gating).

## Design

Three layers. Everything reads tables already in `kipptaf_marts`.

### 1. dbt — resolve one teacher per enrollment (point-in-time)

**Model A — `dim_student_section_enrollment_teachers`**
(`src/dbt/kipptaf/models/marts/dimensions/`). Grain: **one row per
`student_section_enrollment_key`**.

- `dim_student_section_enrollments` LEFT JOIN `bridge_course_section_teachers`
  on `course_section_key`, `role = 'Lead Teacher'`, and a **half-open date
  overlap** of the bridge effective window with the section
  `entry_date`/`exit_date` (`src/dbt/CLAUDE.md` date-range-join rule:
  `start <= x and x < end`).
- Collapse the rare multi-lead case to one row with `dbt_utils.deduplicate`
  (partition by `student_section_enrollment_key`, order by
  `effective_start_date`) — **no** `qualify`/`distinct`.
- Columns: `student_section_enrollment_key` (PK), `student_enrollment_key`,
  `course_section_key`, `teacher_staff_key`, `teacher_role`,
  `teacher_effective_start_date`, `teacher_effective_end_date`, `is_homeroom`
  (`credit_type = 'HR'`). Course/subject attrs are NOT copied here — already
  reachable via the existing
  `student_section_enrollments → course_sections → courses` cube joins.
- Null-wrap `teacher_staff_key` per the nullable-surrogate-key rule; tests:
  `unique` on PK, `relationships` `teacher_staff_key → dim_staff.staff_key`.

**Model B — `dim_student_enrollment_homeroom_teacher`**
(`.../marts/dimensions/`). Grain: **one row per `student_enrollment_key`**.

- From Model A filtered to `is_homeroom`, dedupe to one per
  `student_enrollment_key` (rare mid-year homeroom change → keep earliest).
- Columns: `student_enrollment_key` (PK), `teacher_staff_key`,
  `teacher_effective_start_date`, `teacher_effective_end_date`. Tests: `unique`
  PK, `relationships` to `dim_staff`.

### 2. Cube — two thin teacher cubes, reuse manager cubes

Both `public: false`, named with the `student` prefix (student-domain gating).
Manager join mirrors `staff_work_history` exactly.

**Cube C — `student_section_enrollment_teachers`**
(`src/cube/model/cubes/students/`),
`sql_table: kipptaf_marts.dim_student_section_enrollment_teachers`. Dims:
`student_section_enrollment_key` (PK), `student_enrollment_key`,
`teacher_staff_key`, `teacher_role`, `is_homeroom`,
`teacher_effective_start_date`/`_end_date` (cast TIMESTAMP). Joins
(`many_to_one`): `staff` (on `teacher_staff_key`);
`staff_reporting_relationships` (on `teacher_staff_key` plus
teacher-window/relationship date overlap); `staff_manager` (on
`staff_reporting_relationships.manager_staff_key`).

**Cube D — `student_enrollment_homeroom_teachers`** (same dir),
`sql_table: kipptaf_marts.dim_student_enrollment_homeroom_teacher`. Dims:
`student_enrollment_key` (PK), `teacher_staff_key`, effective dates. Same three
`many_to_one` joins to `staff` / `staff_reporting_relationships` /
`staff_manager`.

### 3. Cube — fact-cube joins and view edits

- `student_attendance.yml`: add `many_to_one` join to
  `student_enrollment_homeroom_teachers` on `student_enrollment_key`.
- `student_assessment_scores.yml`: add `many_to_one` join to
  `student_section_enrollment_teachers` on `student_section_enrollment_key`.

View `join_path` includes (prefix the staff joins so members read
`staff_full_name`, `staff_manager_full_name`, etc.):

- **`student_attendance_detail` / `student_assessment_scores_detail`**: teacher
  plus manager `staff_key`, `full_name`, `first_name`, `last_name`, plus
  `teacher_role` (and `is_homeroom` on assessments). New `Teacher` / `Manager`
  folders.
- **`student_attendance_summary` / `student_assessment_scores_summary`**: only
  non-PII groupers — teacher/manager `staff_key` and `teacher_role`. Names
  excluded (summary carries no PII).

**Access policy**: teacher/manager dimensions follow the same access rules as
all other student data for the school — they sit under the view's existing
`cube-access-student-data` scope; no separate staff-PII tier.

### Fan-out and measure safety (the key risk)

- Fact-to-teacher is `many_to_one` (one row per enrollment after dbt resolution)
  → **no fan-out**; `count_students` / `count_scores` / `avg_daily_attendance`
  unchanged whether or not a teacher dim is in the query.
- `student_attendance` is a SNAPSHOT cube (#4160). We add **dimensions only, no
  measures**, and the join is row-preserving, so the snapshot anchor injection
  is unaffected. Verify a snapshot measure (e.g.
  `count_chronically_absent_year_end`) grouped by teacher returns the same total
  as ungrouped.
- The teacher-to-manager date-overlap join can in rare cases match two reporting
  periods (manager changed mid-assignment) → re-introduces fan. Mitigation: test
  `count_*` grouped-by-manager equals ungrouped on a sample; if it diverges,
  pre-resolve `manager_staff_key` into Models A/B at the teacher-window anchor
  and make the cube manager join a plain degenerate FK.
- Assessments: the fact's `student_section_enrollment_key` already points at the
  subject section (or homeroom fallback per `enrollment_resolution`), so Cube C
  yields the subject teacher automatically; consumers can filter
  `enrollment_resolution = 'subject_section'` for strict subject matches.

## Files

| Action | Path                                                                                                           |
| ------ | -------------------------------------------------------------------------------------------------------------- |
| Create | `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollment_teachers.sql` plus `properties/...yml` |
| Create | `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollment_homeroom_teacher.sql` plus `properties/...yml` |
| Create | `src/cube/model/cubes/students/student_section_enrollment_teachers.yml`                                        |
| Create | `src/cube/model/cubes/students/student_enrollment_homeroom_teachers.yml`                                       |
| Modify | `src/cube/model/cubes/student_attendance/student_attendance.yml` (add join)                                    |
| Modify | `src/cube/model/cubes/student_assessments/student_assessment_scores.yml` (add join)                            |
| Modify | `src/cube/model/views/student_attendance/student_attendance_detail.yml`, `..._summary.yml`                     |
| Modify | `src/cube/model/views/student_assessments/student_assessment_scores_detail.yml`, `..._summary.yml`             |

No `cube.js` change needed (student-prefix naming keeps `isStudentMember` gating
automatic; no new SNAPSHOT cube).

## Implementation order

1. dbt Model A, then Model B (plus properties, tests).
   `uv run dbt build --select dim_student_section_enrollment_teachers dim_student_enrollment_homeroom_teacher --project-dir src/dbt/kipptaf --target dev`.
2. Cubes C and D.
3. Fact-cube joins, then the four view edits plus access policies and folders.

## Verification

- **dbt**: build Models A/B in dev; assert PK uniqueness and FK relationships
  pass. Cross-check in BigQuery: one teacher per
  `student_section_enrollment_key`; homeroom teacher present for current-year
  enrollments; spot-check a known section's Lead Teacher.
- **Cube** (point cube `sql_table` at the dev `zz_<user>_kipptaf_marts` copies
  per `src/cube/CLAUDE.md`, revert before commit): `/sql` compiles the teacher
  plus manager members; `/load` returns teacher/manager for a sample student.
- **Measure safety**: via the cube MCP, confirm `count_students` (attendance)
  and `count_scores` (assessments) are **identical** grouped-by-teacher vs.
  ungrouped over the same filter; repeat for one snapshot measure and for
  grouped-by-manager.
- **Access**: confirm the teacher/manager block is hidden without
  `cube-access-student-data`, exactly like the rest of the student data on the
  view.

## Deferred follow-up (not this spec)

Tiered managers (AP = `Assistant School Leader`, School Leader =
`School Leader`) via the recursive closure `dim_staff_reporting_chain`. That
model is still in an open PR; **defer this extension until it merges to
`kipptaf_marts`**. When it ships, add a per-`staff_key` tier rollup (nearest
ancestor per `position_title` tier) and surface extra manager dimensions on
Cubes C/D — no change to the teacher resolution or fact/view joins built here.
