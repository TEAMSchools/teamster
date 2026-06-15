# Assessment-scores Cube semantic layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Before any cube work, run `Skill` with
> skill=`dbt:using-dbt-for-analytics-engineering` is NOT applicable here — this
> is Cube YAML, not dbt. Read `src/cube/CLAUDE.md` first.

**Goal:** Build the Cube semantic-layer surface over
`fct_assessment_scores_enrollment_scoped` — 7 new cubes, 1 extended cube, and 2
analyst-facing views — so analysts can explore proficiency/mastery across
internal Illuminate interims and NJ/FL state assessments with the full
dimensional chain (standard/skill, subject, source, season, school/region,
course, demographics) and drill from aggregates to row-level scores.

**Architecture:** Cubes are private (`public: false`); views are the only public
surface. The fact cube joins `dates` (completion date),
`assessment_administrations` (season/window + canonical assessment via FK), and
`student_section_enrollments` (the bridge to student, course, location, term).
`dim_dates` is role-played as a second instance `administration_dates` for the
administration date. Student-domain cubes are `student`-prefixed so `cube.js`
`isStudentMember` gating applies; assessment, curriculum, and date dims are
unprefixed.

**Tech Stack:** Cube semantic layer (YAML), BigQuery driver, reading
`kipptaf_marts.*`. Work in the worktree
`/workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer`.

**Anchor issue:** [#4163](https://github.com/TEAMSchools/teamster/issues/4163).

---

## Prerequisites (all met — verify before starting)

- dbt foundation merged (PR #4166): the fact carries `response_type`,
  `response_type_code`, `response_type_description`,
  `response_type_root_description`, `is_replacement`,
  `performance_band_label_number`;
  `dim_assessment_administrations.assessment_key` FK exists;
  `dim_courses.is_foundations` and `dim_student_enrollments.year_in_network`
  exist.
- The 4 marts have been re-materialized into prod `kipptaf_marts` (Dagster run
  `5558a2b6-f39d-41cb-893c-17c961c42529`). **Verify the new columns are live
  before the validation task** (Task 11):

  ```bash
  uv run dbt show --inline "select assessment_key from {{ ref('dim_assessment_administrations') }}" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer/src/dbt/kipptaf --target dev
  ```

  (No trailing `limit` — dbt 1.11/BigQuery rejects it on `--inline`.) If it
  errors with "Name assessment_key not found", the prod rebuild has not
  completed; wait before Task 11.

## Scope notes (data drift since the design spec)

The design spec
([docs/superpowers/specs/2026-06-11-assessment-scores-cube-design.md](../specs/2026-06-11-assessment-scores-cube-design.md))
listed columns that did **not** ship. Exclude them — exposing a column absent
from prod makes the Cube playground error "Name X not found inside Y":

- **`standard_domain`** — dropped from the fact (duplicate `standard_code`
  upstream, [#4172](https://github.com/TEAMSchools/teamster/issues/4172)). Not a
  cube dimension.
- **`status_504`, `is_self_contained`, `is_sipps`** (student_enrollment_status)
  and **`head_of_school`** (locations) — deferred
  ([#4176](https://github.com/TEAMSchools/teamster/issues/4176)). Do not add to
  those cubes or the views.

`cube.yml`'s `cube_semantic_layer.depends_on` already lists every mart these
cubes read (`fct_assessment_scores_enrollment_scoped`,
`dim_assessment_administrations`, `dim_assessments`, `dim_courses`,
`dim_course_sections`, `dim_student_section_enrollments`,
`dim_student_enrollments`, `dim_students`, `dim_locations`, `dim_regions`,
`dim_terms`, `dim_dates`) — **no exposure change is needed**.

## Scope guardrails

- One cube/view per file; `name:` matches filename; no `dim_`/`fct_` prefix on
  cube names. `sql_table` always `kipptaf_marts.<table>`.
- Every cube gets `public: false` at the cube level. Dimensions/measures meant
  for a view get `public: true`. Hidden helper measures prefix `_` +
  `public: false`.
- Joins use cube-reference syntax (`{other.col} = {CUBE}.col`); dim joins from
  facts/dims set `relationship: many_to_one` (or `one_to_one` where 1:1).
- Reserved-word columns (`type`) use backticks in `sql:` (mirror `terms.yml`'s
  `term_type`).
- Time dims cast to `TIMESTAMP`; date-key joins cast through
  (`CAST({CUBE}.<date>_key AS TIMESTAMP)`).
- **Never** open the Cube Playground Models tab (it overwrites hand-authored
  YAML). No deploy step — Cube Cloud redeploys on merge to `main`.
- `git -C <worktree>` for git; name exact files in `git add` (never
  `-u`/`-A`/`.`).
- Validation requires Cube Cloud Dev Mode on the pushed branch (Task 11) — there
  is no local lint beyond trunk yamllint, which each task runs.

---

## Task 1: `administration_dates` cube (role-played `dim_dates`)

A second instance of `dim_dates` for the administration date. Same `sql_table`,
distinct `name:` — this is how Cube role-plays a dim and avoids a diamond
against the fact's `test_date_key` → `dates` join.

**Files:**

- Create: `src/cube/model/cubes/conformed/administration_dates.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: administration_dates
    public: false
    sql_table: kipptaf_marts.dim_dates

    dimensions:
      - name: date_key
        description: Calendar date. Primary key and join target.
        sql: date_key
        type: string
        primary_key: true

      - name: date_day
        description: >-
          Timestamp cast of date_key. Required by Cube for date dimension joins.
        sql: date_timestamp
        type: time
        public: true

      - name: academic_year
        description: >-
          KIPP academic year (July start) the administration date falls in. The
          calendar year the academic year begins (e.g., 2025 for 2025-26).
        sql: academic_year
        type: number
        public: true

      - name: year_number
        description: Calendar year.
        sql: year_number
        type: number
        public: true

      - name: quarter_number
        description: Calendar quarter (1-4).
        sql: quarter_number
        type: number
        public: true

      - name: month_number
        description: Month number (1-12).
        sql: month_number
        type: number
        public: true

      - name: month_name
        description: Full month name (January, February, etc.).
        sql: month_name
        type: string
        public: true
```

- [ ] **Step 2: Trunk-check the file**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/conformed/administration_dates.yml
```

Expected: `No issues`. Fix any yamllint findings (line length, quoting) and
re-check.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/conformed/administration_dates.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add administration_dates role-played date cube

Refs #4163"
```

---

## Task 2: `assessments` cube

Canonical assessment descriptors, read via the administration `assessment_key`
FK. Member-grained for Illuminate; the administration FK resolves to the
canonical-representative member row (spec-verified: 0 title/subject mismatch).

**Files:**

- Create: `src/cube/model/cubes/assessments/assessments.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: assessments
    public: false
    sql_table: kipptaf_marts.dim_assessments

    dimensions:
      - name: assessment_key
        description: >-
          Surrogate key (type, module_code, source_assessment_id, test_type).
          Primary key. Member-grained for Illuminate; canonical for
          state/college/AP.
        sql: assessment_key
        type: string
        primary_key: true

      - name: title
        description: Display name of the assessment.
        sql: title
        type: string
        public: true

      - name: academic_subject
        description: >-
          Subject tested (e.g., Mathematics, English Language Arts, Reading,
          Science).
        sql: academic_subject
        type: string
        public: true

      - name: assessment_type
        description: >-
          Source-system category: illuminate (internal), state_nj, state_fl,
          college, or ap.
        sql: "{CUBE}.`type`"
        type: string
        public: true

      - name: category
        description: >-
          Assessment category by format/content (e.g., CMA, CGI, NJSLA, FAST,
          SAT).
        sql: category
        type: string
        public: true

      - name: module_code
        description: >-
          Module/test code identifying the assessment variant (e.g., QA1, ELA05,
          sat_total_score).
        sql: module_code
        type: string
        public: true

      - name: module_type
        description: >-
          Module type for internal Illuminate assessments (e.g., QA, CR). Null
          for state and college.
        sql: module_type
        type: string
        public: true

      - name: grade_level_tested
        description: >-
          Grade level the assessment targets. Null for college-entrance
          assessments.
        sql: grade_level_tested
        type: number
        public: true

      - name: scope
        description: >-
          How scores link to students: enrollment (tied to a section enrollment)
          or student.
        sql: scope
        type: string
        public: true

      - name: is_internal_assessment
        description: >-
          TRUE for KIPP-created internal assessments via Illuminate; FALSE for
          state and college.
        sql: is_internal_assessment
        type: boolean
        public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/assessments/assessments.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/assessments/assessments.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add assessments dimension cube

Refs #4163"
```

---

## Task 3: `assessment_administrations` cube

Per-occurrence dimension: season/window + administration date + canonical
assessment FK. Joins `administration_dates` (role-played date) and
`assessments`.

**Files:**

- Create: `src/cube/model/cubes/assessments/assessment_administrations.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: assessment_administrations
    public: false
    sql_table: kipptaf_marts.dim_assessment_administrations

    joins:
      - name: administration_dates
        sql: >
          {administration_dates.date_day} = CAST({CUBE}.administered_date_key AS
          TIMESTAMP)
        relationship: many_to_one

      - name: assessments
        sql: "{assessments.assessment_key} = {CUBE}.assessment_key"
        relationship: many_to_one

    dimensions:
      - name: assessment_administration_key
        description: >-
          Surrogate key for the administration occurrence. Primary key.
        sql: assessment_administration_key
        type: string
        primary_key: true

      # FK to assessments — not exposed; descriptors come from the assessments cube.
      - name: assessment_key
        description: FK to assessments (canonical-representative row).
        sql: assessment_key
        type: string

      - name: administration_period
        description: >-
          Scheduling period distinguishing administrations within an academic
          year. NJ state: testing season (Fall, Winter, Spring). FL state: FLDOE
          window. College: College Board round. Null for Illuminate and AP.
        sql: administration_period
        type: string
        public: true

      - name: test_type
        description: >-
          Official vs Practice for college-entrance administrations. Null for
          Illuminate, state, and AP.
        sql: test_type
        type: string
        public: true

      - name: source_assessment_id
        description: >-
          Illuminate assessment id carried to the administration grain (the
          canonical id). Null for non-Illuminate branches.
        sql: source_assessment_id
        type: number
        public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/assessments/assessment_administrations.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/assessments/assessment_administrations.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add assessment_administrations dimension cube

Refs #4163"
```

---

## Task 4: `courses` cube

**Files:**

- Create: `src/cube/model/cubes/courses/courses.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: courses
    public: false
    sql_table: kipptaf_marts.dim_courses

    dimensions:
      - name: course_key
        description: >-
          Surrogate key (course_number, _dbt_source_project). Primary key.
        sql: course_key
        type: string
        primary_key: true

      - name: course_code
        description: PowerSchool course number.
        sql: course_code
        type: string
        public: true

      - name: course_title
        description: Course name.
        sql: course_title
        type: string
        public: true

      - name: academic_subject
        description: >-
          Discipline from the course-subject crosswalk (e.g., Mathematics, ELA).
        sql: academic_subject
        type: string
        public: true

      - name: credit_type
        description: Credit type for the course.
        sql: credit_type
        type: string
        public: true

      - name: is_foundations
        description: >-
          TRUE if this is a Foundations (intervention) course, per the
          course-subject crosswalk.
        sql: is_foundations
        type: boolean
        public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/courses/courses.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/courses/courses.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add courses dimension cube

Refs #4163"
```

---

## Task 5: `course_sections` cube

Joins `courses`. `dim_course_sections.location_key` is left as a degenerate FK
with **no declared join** — location is reached canonically via the student
enrollment (spec-verified that student and section locations never diverge);
joining it here would create a diamond to `locations`.

**Files:**

- Create: `src/cube/model/cubes/courses/course_sections.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: course_sections
    public: false
    sql_table: kipptaf_marts.dim_course_sections

    joins:
      - name: courses
        sql: "{courses.course_key} = {CUBE}.course_key"
        relationship: many_to_one

    dimensions:
      - name: course_section_key
        description: >-
          Surrogate key (sections_dcid, _dbt_source_project). Primary key.
        sql: course_section_key
        type: string
        primary_key: true

      # FK to courses — descriptors come from the courses cube.
      - name: course_key
        description: FK to courses.
        sql: course_key
        type: string

      # Degenerate FK: NOT joined to locations (location is reached via the
      # student enrollment; joining here would diamond against locations).
      - name: location_key
        description: FK to locations. Unused for joins — see comment.
        sql: location_key
        type: string

      - name: identifier
        description: Section number for this class.
        sql: identifier
        type: string
        public: true

      - name: period
        description: >-
          Period expression encoding the days/periods the section meets (e.g.,
          '1(A-F)').
        sql: period
        type: string
        public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/courses/course_sections.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/courses/course_sections.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add course_sections dimension cube

Refs #4163"
```

---

## Task 6: `student_section_enrollments` cube

The bridge from a score's resolved section enrollment to student, course, and
term. `student`-prefixed → inherits `isStudentMember` gating. Joins
`student_enrollments` (reuse — already joins students/locations/status),
`course_sections`, and `terms`.

**Files:**

- Create: `src/cube/model/cubes/students/student_section_enrollments.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: student_section_enrollments
    public: false
    sql_table: kipptaf_marts.dim_student_section_enrollments

    joins:
      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: course_sections
        sql: "{course_sections.course_section_key} = {CUBE}.course_section_key"
        relationship: many_to_one

      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

    dimensions:
      - name: student_section_enrollment_key
        description: >-
          Surrogate key (cc_dcid, _dbt_source_project). Primary key — one row
          per CC record.
        sql: student_section_enrollment_key
        type: string
        primary_key: true

      - name: student_enrollment_key
        description:
          FK to student_enrollments (resolved school enrollment stint).
        sql: student_enrollment_key
        type: string
        public: true

      # FKs — descriptors come from the joined cubes.
      - name: course_section_key
        description: FK to course_sections.
        sql: course_section_key
        type: string

      - name: term_key
        description: FK to terms.
        sql: term_key
        type: string

      - name: academic_year
        description: >-
          KIPP academic year (July start) the section enrollment falls in. The
          calendar year the academic year begins (e.g., 2025 for 2025-26). This
          is the canonical academic_year for the assessment-scores views.
        sql: academic_year
        type: number
        public: true

      - name: entry_date
        sql: CAST(entry_date AS TIMESTAMP)
        type: time
        public: true

      - name: exit_date
        sql: CAST(exit_date AS TIMESTAMP)
        type: time
        public: true

      - name: is_dropped_section
        description: >-
          TRUE if this section enrollment was dropped mid-term (negative section
          id + early exit).
        sql: is_dropped_section
        type: boolean
        public: true

      - name: is_dropped_course
        description: >-
          TRUE if all enrollments for this student x course x year were dropped.
        sql: is_dropped_course
        type: boolean
        public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/students/student_section_enrollments.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/students/student_section_enrollments.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add student_section_enrollments dimension cube

Refs #4163"
```

---

## Task 7: Extend `student_enrollments` cube with `year_in_network`

Additive: one new dimension on the existing cube. (`status_504`,
`is_self_contained`, `is_sipps`, `head_of_school` from the spec are deferred
#4176 — do NOT add them.)

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollments.yml`

- [ ] **Step 1: Add the dimension**

Insert this dimension immediately after the `is_retained_year` dimension block
(before the `measures:` block):

```yaml
- name: year_in_network
  description: >-
    Count of years the student has been enrolled in the network. Populated on
    the student's primary enrollment stint per academic year; null on additional
    same-year stints.
  sql: year_in_network
  type: number
  public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/students/student_enrollments.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/students/student_enrollments.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): expose year_in_network on student_enrollments

Refs #4163"
```

---

## Task 8: `student_assessment_scores` fact cube

The fact. `student`-prefixed → gated. Joins `dates` (completion date),
`assessment_administrations`, `student_section_enrollments`. `count_students`
counts distinct `student_enrollment_key` reached through
`student_section_enrollments`.

**Files:**

- Create: `src/cube/model/cubes/students/student_assessment_scores.yml`

- [ ] **Step 1: Create the cube file**

```yaml
cubes:
  - name: student_assessment_scores
    public: false
    sql_table: kipptaf_marts.fct_assessment_scores_enrollment_scoped

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.test_date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: assessment_administrations
        sql: >
          {assessment_administrations.assessment_administration_key} =
          {CUBE}.assessment_administration_key
        relationship: many_to_one

      - name: student_section_enrollments
        sql: >
          {student_section_enrollments.student_section_enrollment_key} =
          {CUBE}.student_section_enrollment_key
        relationship: many_to_one

    dimensions:
      - name: assessment_score_key
        description: Surrogate key. Primary key for this fact.
        sql: assessment_score_key
        type: string
        primary_key: true

      - name: test_date
        description: >-
          Date the assessment was taken (completion date). Populated for state
          assessments; nullable for internal rows lacking a recorded sitting.
        sql: CAST(test_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: enrollment_resolution
        description: >-
          How the section enrollment was resolved: subject_section or homeroom.
          Filter to subject_section for course/section-level rollups.
        sql: enrollment_resolution
        type: string
        public: true

      - name: proficiency_level
        description: >-
          Proficiency band label (performance band for internal, achievement
          level for state).
        sql: proficiency_level
        type: string
        public: true

      - name: performance_band_label_number
        description: >-
          Numeric ordering of the performance band label within the band scale.
          Null for state assessments.
        sql: performance_band_label_number
        type: number
        public: true

      - name: is_mastery
        description: >-
          TRUE if the student met the mastery/proficiency threshold for this
          assessment.
        sql: is_mastery
        type: boolean
        public: true

      - name: scale_score
        description:
          Scale score achieved. Null for internal (percent-correct) rows.
        sql: scale_score
        type: number
        public: true

      - name: percent_correct
        description: Percent correct. Null for state assessments.
        sql: percent_correct
        type: number
        public: true

      - name: response_type
        description: >-
          Response-type breakdown (e.g., overall, strand, standard). Null for
          state assessments.
        sql: response_type
        type: string
        public: true

      - name: response_type_code
        description: Short code identifying the response type. Null for state.
        sql: response_type_code
        type: string
        public: true

      - name: response_type_description
        description: Human-readable response-type description. Null for state.
        sql: response_type_description
        type: string
        public: true

      - name: response_type_root_description
        description: >-
          Description of the root (top-level) response type. Null for state.
        sql: response_type_root_description
        type: string
        public: true

      - name: is_replacement
        description: >-
          TRUE if this score replaces an earlier attempt. Null for state.
        sql: is_replacement
        type: boolean
        public: true

    measures:
      - name: count_scores
        description: Scored-response count (distinct assessment_score_key).
        sql: assessment_score_key
        type: count_distinct
        public: true

      - name: count_students
        description: >-
          Distinct students (per student-year) with a score in the filtered
          slice.
        sql: "{student_section_enrollments.student_enrollment_key}"
        type: count_distinct
        public: true

      - name: _count_proficient
        sql: assessment_score_key
        type: count_distinct
        public: false
        filters:
          - sql: "{CUBE}.is_mastery = true"

      - name: pct_proficient
        description: >-
          Proficiency/mastery rate — proficient scores / total scores. The
          headline, source-agnostic metric (the only score measure comparable
          across the incompatible scales of internal vs state assessments).
        sql: "1.0 * {_count_proficient} / NULLIF({count_scores}, 0)"
        type: number
        format: percent
        public: true

      - name: avg_percent_correct
        description: >-
          Average percent correct. Internal-effective (null for state) — filter
          by subject/standard for a meaningful value.
        sql: percent_correct
        type: avg
        public: true

      - name: avg_scale_score
        description: >-
          Average scale score. Only meaningful within a single
          assessment/subject/grade/source — scales are not comparable across
          sources.
        sql: scale_score
        type: avg
        public: true
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/cubes/students/student_assessment_scores.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/cubes/students/student_assessment_scores.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add student_assessment_scores fact cube

Refs #4163"
```

---

## Task 9: `student_assessment_scores_summary` view

Aggregates + demographic breakdowns, no direct identifiers. Single
`cube-access-student-data` policy. `academic_year` comes from
`student_section_enrollments` (canonical).

**Files:**

- Create: `src/cube/model/views/students/student_assessment_scores_summary.yml`

- [ ] **Step 1: Create the view file**

```yaml
views:
  - name: student_assessment_scores_summary
    description: >-
      Aggregated assessment proficiency across internal Illuminate interims and
      NJ/FL state assessments. One row per filter slice — never per score.
      pct_proficient (mastery rate) is the headline, source-agnostic metric;
      avg_scale_score and avg_percent_correct are only meaningful within a
      single source/subject/grade. No direct student identifiers — demographic
      dimensions are aggregate breakdowns only. State assessment rows have null
      response_type / percent_correct and null administration_dates by design.

    cubes:
      - join_path: student_assessment_scores
        includes:
          - count_scores
          - count_students
          - pct_proficient
          - avg_percent_correct
          - avg_scale_score
          - enrollment_resolution
          - proficiency_level
          - is_mastery
          - response_type
          - response_type_code
          - response_type_root_description

      - join_path: student_assessment_scores.assessment_administrations.assessments
        prefix: true
        includes:
          - title
          - academic_subject
          - assessment_type
          - category
          - module_code
          - module_type
          - grade_level_tested
          - scope
          - is_internal_assessment

      - join_path: student_assessment_scores.assessment_administrations
        prefix: true
        includes:
          - administration_period
          - test_type

      - join_path: >-
          student_assessment_scores.assessment_administrations.administration_dates
        prefix: true
        includes:
          - academic_year
          - month_number
          - month_name

      - join_path: student_assessment_scores.student_section_enrollments.course_sections.courses
        prefix: true
        includes:
          - academic_subject
          - course_title
          - course_code
          - is_foundations

      - join_path: student_assessment_scores.student_section_enrollments
        prefix: false
        includes:
          - academic_year
          - is_dropped_section
          - is_dropped_course

      - join_path: student_assessment_scores.student_section_enrollments.student_enrollments
        prefix: false
        includes:
          - grade_level
          - graduation_year
          - year_in_network
          - is_retained_year

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.student_enrollment_status
        prefix: false
        includes:
          - is_ell
          - is_iep
          - iep_classification
          - special_education_code
          - special_education_name
          - special_education_placement
          - is_meal_eligible
          - meal_eligibility

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.students
        prefix: false
        includes:
          - gender_identity
          - race
          - is_gifted

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_assessment_scores.student_section_enrollments.terms
        prefix: true
        includes:
          - semester
          - term_name
          - term_code
          - term_type

    meta:
      folders:
        - name: Assessment
          members:
            - assessments_title
            - assessments_academic_subject
            - assessments_assessment_type
            - assessments_category
            - assessments_module_code
            - assessments_module_type
            - assessments_grade_level_tested
            - assessments_scope
            - assessments_is_internal_assessment
            - assessment_administrations_administration_period
            - assessment_administrations_test_type
            - enrollment_resolution
            - proficiency_level
            - is_mastery
            - response_type
            - response_type_code
            - response_type_root_description
        - name: Date
          members:
            - administration_dates_academic_year
            - administration_dates_month_number
            - administration_dates_month_name
        - name: Course
          members:
            - courses_academic_subject
            - courses_course_title
            - courses_course_code
            - courses_is_foundations
        - name: Term
          members:
            - terms_semester
            - terms_term_name
            - terms_term_code
            - terms_term_type
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - gender_identity
            - race
            - is_gifted
        - name: Status
          members:
            - is_ell
            - is_iep
            - iep_classification
            - special_education_code
            - special_education_name
            - special_education_placement
            - is_meal_eligible
            - meal_eligibility
        - name: Enrollment
          members:
            - academic_year
            - grade_level
            - graduation_year
            - year_in_network
            - is_retained_year
            - is_dropped_section
            - is_dropped_course

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, etc.) are
      # aggregate breakdowns only.
      - group: cube-access-student-data
        member_level:
          includes: "*"
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/views/students/student_assessment_scores_summary.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/views/students/student_assessment_scores_summary.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add student_assessment_scores_summary view

Refs #4163"
```

---

## Task 10: `student_assessment_scores_detail` view

Row-level drill-down with student identifiers. Two access policies: PII fields
in `excludes` under `cube-access-student-data`, plus a `cube-access-student-pii`
block with `includes: "*"`. PII fields per project FERPA guidance: `full_name`,
`birth_date`, `lea_student_identifier`, `state_student_identifier`,
`district_student_identifier`, `salesforce_contact_id`.

**Files:**

- Create: `src/cube/model/views/students/student_assessment_scores_detail.yml`

- [ ] **Step 1: Create the view file**

```yaml
views:
  - name: student_assessment_scores_detail
    description: >-
      Row-level assessment scores across internal Illuminate interims and NJ/FL
      state assessments. One row per student x assessment x administration x
      response type. Use for drill-down and individual investigations; for
      roll-ups use student_assessment_scores_summary. pct_proficient (mastery
      rate) is the source-agnostic headline; scale_score is null for internal
      rows and percent_correct is null for state rows. response_type /
      response_type_code carry the standard/skill breakdown. State rows have
      null administration_dates by design (no exact administered date). Contains
      direct student identifiers — see access_policy for PII gating.

    cubes:
      - join_path: student_assessment_scores
        includes:
          - count_scores
          - count_students
          - pct_proficient
          - avg_percent_correct
          - avg_scale_score
          - assessment_score_key
          - test_date
          - enrollment_resolution
          - proficiency_level
          - performance_band_label_number
          - is_mastery
          - scale_score
          - percent_correct
          - response_type
          - response_type_code
          - response_type_description
          - response_type_root_description
          - is_replacement

      - join_path: student_assessment_scores.assessment_administrations.assessments
        prefix: true
        includes:
          - title
          - academic_subject
          - assessment_type
          - category
          - module_code
          - module_type
          - grade_level_tested
          - scope
          - is_internal_assessment

      - join_path: student_assessment_scores.assessment_administrations
        prefix: true
        includes:
          - administration_period
          - test_type
          - source_assessment_id

      - join_path: >-
          student_assessment_scores.assessment_administrations.administration_dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_number
          - month_name

      - join_path: student_assessment_scores.student_section_enrollments.course_sections.courses
        prefix: true
        includes:
          - academic_subject
          - course_title
          - course_code
          - credit_type
          - is_foundations

      - join_path: student_assessment_scores.student_section_enrollments.course_sections
        prefix: true
        includes:
          - identifier
          - period

      - join_path: student_assessment_scores.student_section_enrollments
        prefix: false
        includes:
          - student_section_enrollment_key
          - student_enrollment_key
          - academic_year
          - entry_date
          - exit_date
          - is_dropped_section
          - is_dropped_course

      - join_path: student_assessment_scores.student_section_enrollments.student_enrollments
        prefix: false
        includes:
          - grade_level
          - graduation_year
          - year_in_network
          - is_retained_year

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.student_enrollment_status
        prefix: false
        includes:
          - is_ell
          - is_iep
          - iep_classification
          - special_education_code
          - special_education_name
          - special_education_placement
          - is_meal_eligible
          - meal_eligibility

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.students
        prefix: false
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - district_student_identifier
          - salesforce_contact_id
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: >-
          student_assessment_scores.student_section_enrollments.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_assessment_scores.student_section_enrollments.terms
        prefix: true
        includes:
          - semester
          - term_name
          - term_code
          - term_type

    meta:
      folders:
        - name: Assessment
          members:
            - assessments_title
            - assessments_academic_subject
            - assessments_assessment_type
            - assessments_category
            - assessments_module_code
            - assessments_module_type
            - assessments_grade_level_tested
            - assessments_scope
            - assessments_is_internal_assessment
            - assessment_administrations_administration_period
            - assessment_administrations_test_type
            - assessment_administrations_source_assessment_id
            - test_date
            - enrollment_resolution
            - proficiency_level
            - performance_band_label_number
            - is_mastery
            - scale_score
            - percent_correct
            - response_type
            - response_type_code
            - response_type_description
            - response_type_root_description
            - is_replacement
        - name: Date
          members:
            - administration_dates_date_day
            - administration_dates_academic_year
            - administration_dates_month_number
            - administration_dates_month_name
        - name: Course
          members:
            - courses_academic_subject
            - courses_course_title
            - courses_course_code
            - courses_credit_type
            - courses_is_foundations
            - course_sections_identifier
            - course_sections_period
        - name: Term
          members:
            - terms_semester
            - terms_term_name
            - terms_term_code
            - terms_term_type
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - student_key
            - full_name
            - birth_date
            - lea_student_identifier
            - state_student_identifier
            - district_student_identifier
            - salesforce_contact_id
            - gender_identity
            - race
            - enrollment_status
            - is_gifted
        - name: Status
          members:
            - is_ell
            - is_iep
            - iep_classification
            - special_education_code
            - special_education_name
            - special_education_placement
            - is_meal_eligible
            - meal_eligibility
        - name: Enrollment
          members:
            - student_section_enrollment_key
            - student_enrollment_key
            - academic_year
            - entry_date
            - exit_date
            - grade_level
            - graduation_year
            - year_in_network
            - is_retained_year
            - is_dropped_section
            - is_dropped_course

    access_policy:
      - group: cube-access-student-data
        member_level:
          includes: "*"
          excludes:
            - full_name
            - birth_date
            - lea_student_identifier
            - state_student_identifier
            - district_student_identifier
            - salesforce_contact_id
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Trunk-check**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer && /workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/views/students/student_assessment_scores_detail.yml
```

Expected: `No issues`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer add src/cube/model/views/students/student_assessment_scores_detail.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer commit -m "feat(cube): add student_assessment_scores_detail view

Refs #4163"
```

---

## Task 11: Validate on Cube Cloud Dev Mode + cross-check against the warehouse

No local Cube compile is reliable here — validate on the pushed branch via Cube
Cloud Dev Mode. **Confirm the prod rebuild landed first** (Prerequisites block).

**Files:** none (validation + fixes).

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer push origin cristinabaldor/feat/claude-assessment-scores-cube-layer
```

- [ ] **Step 2: Spin up Dev Mode for the branch**

In Cube Cloud → Data Model → Dev Mode → add the branch
`cristinabaldor/feat/claude-assessment-scores-cube-layer`. (Branch staging envs
don't auto-create; verify `GOOGLE_DIRECTORY_SA_KEY` /
`GOOGLE_DIRECTORY_SA_SUBJECT` are set on the env if API errors appear.)

- [ ] **Step 3: Compile each view via `/sql`**

Compile a query for each view (`/sql` succeeds even against `public: false`
members, so it isolates model/schema errors from access gating). For each of
`student_assessment_scores_summary` and `student_assessment_scores_detail`,
request `pct_proficient` grouped by `assessments_academic_subject` and
`regions_region_name`. Expected: SQL compiles with no "Name X not found" errors.
A `WHERE (1 = 0)` + `rlsAccessDenied` means a missing `cube-*` group on the dev
identity, not a model bug.

- [ ] **Step 4: Verify each fact-cube FK populates (not 100% NULL)**

Run in the worktree (prod data):

```bash
uv run dbt show --inline "select countif(assessment_administration_key is null) as n_adm_null, countif(student_section_enrollment_key is null) as n_sse_null, count(*) as n_total from {{ ref('fct_assessment_scores_enrollment_scoped') }}" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer/src/dbt/kipptaf --target dev
```

Expected: both null counts far below `n_total`. `administration_dates` will be
null for state rows by design — that is expected, not a broken join.

- [ ] **Step 5: Validate `pct_proficient` against direct warehouse SQL**

Compute the mastery rate directly and compare to the view's number for one slice
(e.g. `response_type_code` x `region` x `academic_year`):

```bash
uv run dbt show --inline "select countif(is_mastery) / count(*) as pct_proficient, count(*) as n from {{ ref('fct_assessment_scores_enrollment_scoped') }} where response_type_code is not null" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube-layer/src/dbt/kipptaf --target dev
```

Expected: matches the Cube `pct_proficient` for the same filter within rounding.
If it diverges, check the `_count_proficient` filter (`is_mastery = true`) and
the `count_scores` grain.

- [ ] **Step 6: If any view failed to compile, fix the offending cube/view and
      re-push**

Bundle fixes into one push (pushing restarts any in-progress Cube redeploy).
Re-run Steps 3–5 until clean.

---

## Task 12: Open the PR

**Files:** none.

- [ ] **Step 1: Open the PR** using `.github/pull_request_template.md` as the
      body, `Refs #4163` in the body (auto-links the project board — do NOT
      `gh project item-add` the PR). Title:
      `feat(cube): assessment-scores semantic layer`.

- [ ] **Step 2:** After Cube Cloud's branch check passes, confirm the two views
      appear and compile. Note in the PR description that the dbt foundation
      (#4166) is merged and the new columns are materialized in prod.

---

## Self-review notes

**Spec coverage** (against `2026-06-11-assessment-scores-cube-design.md`):

- 7 new cubes: `administration_dates` (T1), `assessments` (T2),
  `assessment_administrations` (T3), `courses` (T4), `course_sections` (T5),
  `student_section_enrollments` (T6), `student_assessment_scores` fact (T8). ✅
- Extended cube: `student_enrollments` + `year_in_network` (T7). ✅ The spec's
  other extensions (`student_enrollment_status` status_504/is_self_contained/
  is_sipps; `locations` head_of_school) are **deferred #4176** — intentionally
  excluded (see Scope notes).
- 2 views: summary (T9), detail (T10). ✅ Member-drilldown view deferred
  (#4170).
- Measures: `count_scores`, `count_students`, `pct_proficient` (+ helper
  `_count_proficient`), `avg_percent_correct`, `avg_scale_score`. ✅
- Role-play / diamond resolutions: `dim_dates` role-played as
  `administration_dates` (T1); `course_sections.location_key` degenerate, no
  join (T5); canonical assessment via the administration FK, not a direct fact
  FK (T3); `academic_year` canonical from `student_section_enrollments` (T6,
  surfaced in views). ✅
- Exposures: all marts already in `cube.yml` depends_on — verified, no change.

**Excluded vs spec (data drift, would error in the playground):**
`standard_domain` (dropped #4172); `status_504`, `is_self_contained`,
`is_sipps`, `head_of_school` (deferred #4176).

**Type consistency:** join keys verified against mart property YAML — every FK
column (`assessment_administration_key`, `student_section_enrollment_key`,
`test_date_key`, `assessment_key`, `administered_date_key`,
`student_enrollment_key`, `course_section_key`, `course_key`, `term_key`) exists
on the named mart; reserved word `type` is backticked as `assessment_type`.
