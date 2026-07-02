# Link Student-Data Domains to Responsible Teacher — Cube Design

**Date:** 2026-06-26 (revised 2026-07-01) **Status:** Active **Branch:**
`cristinabaldor/feat/claude-student-teacher-manager-cube-linkage` **Issue:**
[#4273](https://github.com/TEAMSchools/teamster/issues/4273)

## Context

Analysts need to slice student-data views by the **responsible teacher**
(point-in-time) and to answer teacher-roster questions:

- **Attendance** → the student's **homeroom/advisory** teacher.
- **Assessments** → the **subject-area section lead** for each kid.
- **Headcount** → "how many students does this teacher teach?" (homeroom and
  section).
- **Class roster** → the student list for a teacher's section(s).
- Later (out of scope here, but the primitive is reused): gradebooks and other
  section-scoped student data.

The teacher's **manager and reporting chain** are deferred
([Deferred](#deferred-blocked-on-4269)); the **co-lead / co-teacher** breakdown
is a separate follow-up
([Follow-up](#follow-up-co-taught--multi-lead-sections)).

Confirmed decisions: both domains in one spec; Lead Teacher only;
enrollment-grain anchor; bridge as the teacher source; single lead teacher this
PR (co-teacher breakdown and manager/chain deferred); headcount + roster folded
into this PR.

## Why the resolution must live in dbt, not a Cube join

The obvious question is whether Cube can just join a fact to the teacher tables
and skip new dbt work. Cube _can_ host multi-table joins inline —
`staff_work_history.yml` does a 7-table SCD2 period-intersection in inline
`sql:`. The blocker is narrower:

- **Uniqueness must be _enforced_, and only dbt can do that.** Resolving the
  responsible teacher requires filtering to `Lead Teacher`, overlapping dates,
  then **deduplicating** sections with more than one lead to a single value.
  Cube has no window functions and no dedup, and its `many_to_one` fan-trap
  protection **trusts the declared relationship** rather than verifying it — a
  Cube-only join that is not perfectly 1:1 silently double-counts attendance
  days and assessment scores. dbt is where the value is deduped **and** pinned
  with a `unique` test. That test is the entire safety guarantee.
- **The fact-to-teacher path spans a derived grain.** Attendance is keyed on
  `student_enrollment_key` with no section key at all; "homeroom teacher" is a
  derived path (enrollment → `HR`-credit section → lead teacher) that does not
  exist as joinable keys.

The resolution therefore lives in dbt. But it does **not** need new `dim_`
models or new cubes — it is columns on the two enrollment dims that already back
the cubes wired into these views (below).

## Teacher source: `bridge_course_section_teachers` (validated)

The teacher resolves from `bridge_course_section_teachers`
(`role = 'Lead Teacher'`), **not** the legacy PowerSchool teacher-of-record path
the Tableau dashboards use (`int_powerschool__advisory` for homeroom;
`base_powerschool__course_enrollments.teachernumber` for assessments).
Rationale:

- The bridge is the marts-native primitive: it is **already keyed on
  `staff_key`** (via `int_people__staff_roster`), which is exactly what Cube's
  `staff` cube joins on. The legacy path emits a raw `teachernumber` that would
  need the same crosswalk re-derived to reach Cube.
- The bridge is **role-aware** (`Lead Teacher` vs `Co-teacher` /
  `Gradebook Access`), so it names the actual lead in a co-taught room; the
  legacy teacher-of-record does not distinguish.

**Validation (enrollment-weighted agreement, bridge Lead Teacher vs legacy
teacher-of-record, where both assign a teacher):**

| Year    | Section kind         | Enrollments | Agreement |
| ------- | -------------------- | ----------- | --------- |
| 2025-26 | HR (homeroom)        | 10,883      | 98.1%     |
| 2025-26 | non-HR (assessments) | 66,032      | 94.8%     |
| 2024-25 | HR (homeroom)        | 10,674      | 98.4%     |
| 2024-25 | non-HR (assessments) | 65,403      | 97.8%     |

Two consequences carried into the design:

- **Cube will not reconcile row-for-row with the Tableau dashboards** in
  co-taught / multi-lead sections (~2% of homeroom, ~2–5% of academic-section
  enrollments). The divergence is the bridge being _more_ precise about the lead
  teacher, not a defect. Flag this to analysts who compare the two surfaces.
- **A `NULL` teacher is expected** for a minority of enrollments (~4% homeroom,
  ~7–8% academic sections): neither source assigns a teacher. The teacher FK is
  nullable by design (null-wrapped surrogate).

## Anchor: enrollment-grain, not event-date

The teacher is a **dimensional attribute of the enrollment**, not a per-event
measurement. The existing Tableau dashboards are already enrollment-grain —
`rpt_tableau__attendance_dashboard` attaches one advisor per enrollment, and
`rpt_tableau__assessment_dashboard` picks one section per
`(student, year, subject)` (`rn_student_year_illuminate_subject_desc = 1`),
neither anchored to the test/attendance date. An event-date anchor (teacher as
of the day the test was taken) is technically possible — assessments carry an
administration date — but it would be a new, divergent per-fact measurement, not
a reusable dimension, and would be far heavier on the daily attendance fact for
a vanishingly small set of mid-year-handoff days. Enrollment-grain replicates
the established behavior and yields one reusable column per dim (also feeding
the headcount, roster, and future gradebook use cases).

Handoff sections (>1 lead overlapping the enrollment — ~5.5% of academic-section
enrollments when weighted by students) collapse to one value by
`dbt_utils.deduplicate` ordering `effective_start_date desc` (most-recent lead —
matches the dashboards' most-recent-section convention and picks the current
teacher).

## Confirmed facts (from data and code exploration)

- `bridge_course_section_teachers` (`kipptaf_marts`): grain section x teacher x
  period; cols `course_section_key`, `staff_key`, `role`,
  `effective_start_date`, `effective_end_date`. Built from
  `stg_powerschool__sectionteacher` + `stg_powerschool__roledef` +
  `int_people__staff_roster` (which supplies `staff_key`). `role` values:
  `Lead Teacher`, `Co-teacher`, `Gradebook Access (edit)`, `Blended Learning`,
  `Job Share Teacher`, `PhysEd Share`.
- `dim_student_section_enrollments` (grain `student_section_enrollment_key`):
  FKs `student_enrollment_key`, `course_section_key`; `entry_date`, `exit_date`,
  `is_dropped_section`. Already reads `base_powerschool__course_enrollments` and
  is read by the `student_section_enrollments` cube — which has **no measures
  today**. `dim_courses.credit_type = 'HR'` marks homeroom courses.
- `dim_student_enrollments` (grain `student_enrollment_key`): the school-stint
  dim. Read by the `student_school_enrollments` cube (which has
  `count_enrollments`, a stint count — not a headcount).
- `student_enrollments` cube reads `fct_student_attendance_daily` and owns
  `count_students` (the point-in-time headcount, `count_distinct`); it backs the
  existing `student_enrollments_detail` / `student_enrollments_summary` views.
- `fct_assessment_scores_enrollment_scoped`: FK `student_section_enrollment_key`
  (already subject-resolved) plus `enrollment_resolution` value
  `subject_section` or `homeroom`. Its cube already joins `many_to_one` to
  `student_section_enrollments`.
- `fct_student_attendance_daily`: daily grain, FK `student_enrollment_key`
  (school stint, **no section key**). Its cubes already join `many_to_one` to
  `student_school_enrollments`. A SNAPSHOT cube.
- Cube conventions: cubes `public: false`, views public; derived grains / dedup
  / multi-table resolution live in dbt read via `sql_table`; student-domain
  cubes are named `student*` (drives `isStudentMember` gating).

## Design

Everything reads tables already in `kipptaf_marts`. **No new dbt models, no new
cubes** — the fact-to-enrollment joins already exist. One **new roster view** is
added (§4).

### 1. dbt — resolve one teacher per enrollment

**`dim_student_section_enrollments`** — add resolved columns (grain unchanged:
one row per `student_section_enrollment_key`):

- LEFT JOIN `bridge_course_section_teachers` on `course_section_key`,
  `role = 'Lead Teacher'`, and a **half-open date overlap** of the bridge
  effective window with the section `entry_date`/`exit_date`
  (`src/dbt/CLAUDE.md` date-range-join rule: `start <= x and x < end`).
- Collapse handoff sections to one value with `dbt_utils.deduplicate` (partition
  by `student_section_enrollment_key`, order by `effective_start_date desc` —
  most-recent) — **no** `qualify`/`distinct`.
- New columns: `lead_teacher_staff_key`, `teacher_role`.
- Null-wrap `lead_teacher_staff_key` per the nullable-surrogate-key rule (the
  ~7–8% coverage gap is real, not an error); add a `relationships` test
  `lead_teacher_staff_key -> dim_staff.staff_key`. The dim's existing PK
  `unique` test guarantees the added columns did not change the grain (the
  fan-out guard).

**`dim_student_enrollments`** — add `homeroom_teacher_staff_key` (grain
unchanged: one row per `student_enrollment_key`):

- Resolve the stint's `HR`-credit section (`dim_courses.credit_type = 'HR'`),
  then its `Lead Teacher` from the bridge, deduped to one value per
  `student_enrollment_key` (rare mid-year homeroom change → most-recent). The
  resolution SQL may live in a supporting `int_` model that this dim reads
  rather than inline — an implementation-plan detail.
- New column: `homeroom_teacher_staff_key` (nullable, null-wrapped).
  `relationships` test to `dim_staff.staff_key`; existing PK `unique` test is
  the fan-out guard.

### 2. Cube — widen the two existing dim cubes (+ one measure)

No new cubes. Each existing dim cube exposes the teacher FK and gains one
`many_to_one` join to `staff` for the teacher name.

- **`student_section_enrollments`** — add dims `lead_teacher_staff_key` (FK,
  degenerate) and `teacher_role`; add join `many_to_one` to `staff` on
  `lead_teacher_staff_key` (prefixed so members read `staff_full_name` etc.).
  **Add a `count_students` measure** (`count_distinct` on the student, reached
  via the existing `student_school_enrollments` join) — this is what answers
  "how many students does this section teacher teach?" and is fan-safe.
- **`student_school_enrollments`** (reads `dim_student_enrollments`) — add dim
  `homeroom_teacher_staff_key`; add the same `many_to_one` join to `staff`.

The fact cubes (`student_attendance`, `student_assessment_scores`,
`student_enrollments`) are **unchanged** — they already join to these enrollment
cubes.

### 3. Cube — edits to existing views

Add teacher members (prefix the `staff` join so members read `staff_full_name`,
etc.). New `Teacher` folder on each view. All under the view's existing
`cube-access-student-data` scope.

- **`student_attendance_detail` / `..._summary`** — homeroom teacher (detail:
  name + `staff_key`; summary: `staff_key` grouper).
- **`student_assessment_scores_detail` / `..._summary`** — section lead teacher
  (detail: name + `staff_key` + `teacher_role`; summary: `staff_key` +
  `teacher_role`).
- **`student_enrollments_detail` / `..._summary`** — homeroom teacher. With the
  cube's existing `count_students`, this answers homeroom headcount ("students
  in this teacher's advisory") and, via detail, the **advisory roster**.

### 4. Cube — new `student_section_enrollments` roster view

A per-teacher **class roster** and section headcount need a section-grained
analyst surface, which does not exist today. Add
`student_section_enrollments_detail` and `student_section_enrollments_summary`
(`src/cube/model/views/students/`):

- **Detail**: section (course/section descriptors via existing joins), lead
  teacher (name + `staff_key` + `teacher_role`), student identity, `entry_date`
  / `exit_date`, `is_dropped_section`, and the new `count_students` measure.
  Filtering to a teacher yields their class roster; grouping by teacher yields
  per-teacher headcount. Carries student PII → two access blocks
  (`cube-access-student-data` with PII excludes + `cube-access-student-pii`),
  per the detail-view pattern.
- **Summary**: non-PII groupers (teacher `staff_key`, `teacher_role`, section,
  `academic_year`) + `count_students`. Single `cube-access-student-data` block.

### Fan-out and measure safety (the key risk)

- Fact/enrollment-to-teacher is `many_to_one` (one value per enrollment after
  dbt resolution) → **no fan-out**; `count_students` / `count_scores` /
  `avg_daily_attendance` unchanged whether or not the teacher dim is in the
  query.
- The new section `count_students` is `count_distinct` on the student, so it is
  correct at every grouping (per-teacher and grand total) even before the
  co-teacher follow-up introduces fan.
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

| Action | Path                                                                                |
| ------ | ----------------------------------------------------------------------------------- |
| Modify | `dim_student_section_enrollments.sql` plus its `.yml` (marts/dimensions)            |
| Modify | `dim_student_enrollments.sql` plus its `.yml` (marts/dimensions)                    |
| Modify | `src/cube/model/cubes/students/student_section_enrollments.yml` (dims, join, count) |
| Modify | `src/cube/model/cubes/students/student_school_enrollments.yml` (dim, join)          |
| Modify | `views/student_attendance/student_attendance_detail.yml`, `..._summary.yml`         |
| Modify | `views/student_assessments/student_assessment_scores_detail.yml`, `..._summary.yml` |
| Modify | `views/students/student_enrollments_detail.yml`, `..._summary.yml`                  |
| Create | `views/students/student_section_enrollments_detail.yml`, `..._summary.yml`          |

Possibly one new `int_` helper model feeding the homeroom resolution
(implementation-plan call). No `cube.js` change (existing student-prefixed cubes
keep their `isStudentMember` gating; no new SNAPSHOT cube).

## Implementation order

1. dbt: resolve `lead_teacher_staff_key` / `teacher_role` on
   `dim_student_section_enrollments`, then `homeroom_teacher_staff_key` on
   `dim_student_enrollments` (plus properties, tests).
   `uv run dbt build --select dim_student_section_enrollments dim_student_enrollments --project-dir src/dbt/kipptaf --target dev`.
2. Cube: widen `student_section_enrollments` (+ `count_students`) and
   `student_school_enrollments`.
3. Edit the six existing views; create the two new roster views with access
   policies and folders.

## Verification

- **dbt**: build the two dims in dev; assert PK uniqueness still holds and the
  new `relationships` tests pass. Cross-check in BigQuery: one teacher per
  `student_section_enrollment_key`; homeroom teacher present for current-year
  enrollments; spot-check a known section's Lead Teacher; confirm the
  null-teacher share is in the expected ~4–8% band (not a broken join).
- **Cube** (point cube `sql_table` at the dev `zz_<user>_kipptaf_marts` copies
  per `src/cube/CLAUDE.md`, revert before commit): `/sql` compiles the teacher
  members and the section `count_students`; `/load` returns the teacher and a
  class roster for a sample teacher.
- **Measure safety**: via the cube MCP, confirm `count_students` (attendance,
  enrollments, section) and `count_scores` (assessments) are **identical**
  grouped-by-teacher vs. ungrouped over the same filter; repeat for one snapshot
  measure.
- **Access**: confirm the teacher block and the new roster detail view are
  hidden without `cube-access-student-data`, and roster PII without
  `cube-access-student-pii`.

## Follow-up: co-taught / multi-lead sections

This spec resolves **one** Lead Teacher per enrollment (most-recent on a
handoff), which under-represents **co-taught / multi-lead sections** — exactly
where Cube diverges from the Tableau dashboards (~2% homeroom, ~2–5% academic;
~5.5% of academic-section enrollments sit in a >1-lead section). Analysts want
both to **group by** every teacher (incl. co-teachers, by role) and to
**filter** to a teacher's sections. Design worked out for that follow-up:

- **Isolate the fan.** Keep the existing views on the single-lead `many_to_one`
  field (fully additive, no fan). Add a **dedicated teacher-attribution view per
  domain**, backed by a new **many-to-many bridge cube** (section-enrollment ×
  teacher × `role`, `one_to_many` from the enrollment). Do NOT put the fanning
  join on the ADA/average-bearing views.
- **One surface serves both needs.** A single-teacher _filter_ on the bridge
  view does not fan (only that teacher's rows match → each student once → all
  measures correct, including averages). Fan-out only bites a genuine _group-by_
  across teachers, and only in cross-teacher totals.
- **Measure audit on the bridge view.** Reformulate every flag/count additive to
  `count_distinct(fact_PK)` filtered by the flag (`count_scores` →
  `count_distinct(assessment_score_key)`; `count_absent_days` →
  `count_distinct(student_attendance_daily_key)` filtered `is_absent = 1`;
  `_sum_proficient` / `_sum_tardy` / `_count_present_days` likewise). Because
  the PK is unique these return identical values on the non-fan path — a pure
  robustness upgrade — and stay correct under fan. Reformulate numerator and
  denominator of each ratio together.
- **Residue to decide.** Continuous-sum ratios (`avg_daily_attendance`,
  `avg_scale_score`, `avg_percent_correct`) cannot be count-distinct'd. They are
  correct per-teacher and for single-teacher filters, but their cross-teacher
  grand total is fan-weighted. Either expose with a "don't read the all-teachers
  total" description or omit them from the teacher-attribution view.
- **Pre-agg note.** Exact `count_distinct` is non-additive for pre-aggregations;
  switch to `count_distinct_approx` (HLL) if those views get pre-aggregated.

Track this as its own issue (linked to #4273) with the fan-out analysis above.

## Deferred (blocked on #4269)

Manager and reporting-chain linkage — direct manager, plus AP
(`Assistant School Leader`) and School Leader tiers — is deferred until
[#4269](https://github.com/TEAMSchools/teamster/pull/4269) merges. That PR
introduces `dim_staff_reporting_chain` (the transitive org closure) and
`dim_staff_cube_access`. The point-in-time anchoring approach for the manager
join is **TBD** and will be decided when that model lands (we may take a
different route entirely). The teacher `staff_key` resolved here is the join
anchor; adding managers will not rework the teacher layer built in this spec.
