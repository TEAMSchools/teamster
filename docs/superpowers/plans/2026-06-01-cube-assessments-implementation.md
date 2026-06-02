# Cube Assessments Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement three new cube files and four new view files for the
assessments domain in the Cube semantic layer. Two student-scoped fact cubes
(enrollment-scoped and student-scoped) each inline their bridge table into the
`sql:` block. One conformed dimension cube (`assessment_administrations`) wraps
`dim_assessment_administrations` as a standalone join target. Four views expose
the fact cubes to analysts with appropriate detail/summary splits and access
policies.

**Architecture:** All new files are in `src/cube/`. No dbt changes required. The
bridge tables have no independent analytical grain — they are lookup bridges
inlined into the fact cube SQL blocks. `dim_assessment_administrations` is a
standalone grain (assessment × occurrence context) and gets its own cube file.
Both fact cubes join `assessment_administrations` on
`assessment_administration_key`. Both fact cubes are student-domain cubes
(`student_` prefix), making them automatically subject to `isStudentMember`
`queryRewrite` enforcement.

**Prerequisite:** Plan `2026-06-01-cube-model-yaml-implementation.md` (plan 0)
has already run. All conformed cubes and student-domain cubes use the unprefixed
naming convention; `cube.js` has `isStudentMember`/`isStaffMember` helpers and
`withSyntheticGroups`.

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

**Source dbt models read:**

- `kipptaf_marts.fct_assessment_scores_enrollment_scoped`
- `kipptaf_marts.fct_assessment_scores_student_scoped`
- `kipptaf_marts.dim_assessment_administrations`
- `kipptaf_marts.bridge_assessment_expectations_enrollment_scoped`
- `kipptaf_marts.bridge_assessment_expectations_student_scoped`

---

## Task 1: `assessment_administrations` conformed dimension cube

The `dim_assessment_administrations` mart has six columns in its final SELECT:
`assessment_administration_key`, `administered_date_key`, `_dbt_source_project`,
`administration_period`, `source_assessment_id`, and `test_type`. The analytical
attributes (`assessment_type`, `title`, `subject_area`, `scope`, `module_code`,
`grade_level`) are hash inputs only and are NOT in the mart output. The dim gets
its own cube file because it has a standalone administration-event grain that
both fact cubes join on. No `student_` prefix — it is a conformed dimension, not
a student-domain cube.

`administered_date_key` is nullable (NULL for state/AP sources that only record
academic year + administration period). The `dates` join must be declared but
will produce LEFT-JOIN semantics for NULL-keyed rows — declare
`relationship: many_to_one` and let analysts filter on `administration_period`
for rows without an exact date.

**Files:**

- Create: `src/cube/model/cubes/assessments/assessment_administrations.yml`

- [ ] **Step 1: Create the cube file**

Write the following as the complete content of
`src/cube/model/cubes/assessments/assessment_administrations.yml`:

```yaml
cubes:
  - name: assessment_administrations
    public: false
    sql_table: kipptaf_marts.dim_assessment_administrations

    joins:
      - name: dates
        sql: >
          {dates.date_day} = CAST({CUBE}.administered_date_key AS TIMESTAMP)
        relationship: many_to_one

    dimensions:
      - name: assessment_administration_key
        sql: assessment_administration_key
        type: string
        primary_key: true

      - name: administered_date
        sql: CAST(administered_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: source_project
        sql: _dbt_source_project
        type: string
        public: true

      - name: administration_period
        sql: administration_period
        type: string
        public: true

      - name: source_assessment_id
        sql: source_assessment_id
        type: number
        public: true

      - name: test_type
        sql: test_type
        type: string
        public: true

      # Derived directly on the cube — avoids a two-hop .dates join that would
      # produce dates_academic_year (same prefix as the fact's direct dates path,
      # causing a member name collision in views that include both).
      - name: academic_year
        sql: >
          EXTRACT(YEAR FROM administered_date_key) + IF(EXTRACT(MONTH FROM
          administered_date_key) >= 7, 0, -1)
        type: number
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/assessments/assessment_administrations.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('dimensions:', [d['name'] for d in cube['dimensions']])
"
```

Expected output:

```text
cube name: assessment_administrations
public: False
dimensions: ['assessment_administration_key', 'administered_date', 'source_project', 'administration_period', 'source_assessment_id', 'test_type']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/assessments/assessment_administrations.yml
git commit -m "feat(cube): add assessment_administrations conformed dimension cube"
```

---

## Task 2: `student_assessments_enrollment_scoped` fact cube

Pattern 2 (fact-based domain cube) with `sql:` instead of `sql_table:` because
the bridge table is inlined. The bridge
(`bridge_assessment_expectations_enrollment_scoped`) joins via
`(assessment_administration_key, student_section_enrollment_key)` — both columns
appear in the fact. The bridge adds only the `assessment_expectation_key` (used
as the mastery-denominator dimension) and no other analytical columns. The LEFT
JOIN means rows with no expectation record (state assessments not in the bridge)
still appear — only internal Illuminate assessments with a resolvable section
enrollment have expectation rows.

Column list from dbt facts YAML: `assessment_score_key`,
`assessment_administration_key`, `student_key`, `test_date_key`, `scale_score`,
`percent_correct`, `proficiency_level`, `is_mastery`. The bridge adds
`assessment_expectation_key`.

Joins from this cube: `dates` (on `test_date_key`), `assessment_administrations`
(on `assessment_administration_key`), `students` (on `student_key`). No direct
`student_enrollments` join — this fact is keyed by `student_key`, not
`student_enrollment_key`.

`is_mastery` is BOOLEAN in dbt. Cube `type: boolean` dimensions are not directly
summable. Expose it as a boolean dimension and compute mastery-rate measures
using COUNT DISTINCT with a filter.

**Files:**

- Create:
  `src/cube/model/cubes/assessments/student_assessments_enrollment_scoped.yml`

- [ ] **Step 1: Create the cube file**

Write the following as the complete content of
`src/cube/model/cubes/assessments/student_assessments_enrollment_scoped.yml`:

```yaml
cubes:
  - name: student_assessments_enrollment_scoped
    public: false
    sql: |
      SELECT
        f.assessment_score_key,
        f.assessment_administration_key,
        f.student_key,
        f.test_date_key,
        f.scale_score,
        f.percent_correct,
        f.proficiency_level,
        f.is_mastery,
        b.assessment_expectation_key,
      FROM kipptaf_marts.fct_assessment_scores_enrollment_scoped f
      LEFT JOIN kipptaf_marts.bridge_assessment_expectations_enrollment_scoped b
        ON b.assessment_administration_key = f.assessment_administration_key
        AND b.student_section_enrollment_key = f.student_key

    joins:
      - name: dates
        sql: >
          {dates.date_day} = CAST({CUBE}.test_date_key AS TIMESTAMP)
        relationship: many_to_one

      - name: assessment_administrations
        sql: >
          {assessment_administrations.assessment_administration_key} =
          {CUBE}.assessment_administration_key
        relationship: many_to_one

      - name: students
        sql: "{students.student_key} = {CUBE}.student_key"
        relationship: many_to_one

    dimensions:
      - name: assessment_score_key
        sql: assessment_score_key
        type: string
        primary_key: true

      - name: test_date
        sql: CAST(test_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: scale_score
        sql: scale_score
        type: number
        public: true

      - name: percent_correct
        sql: percent_correct
        type: number
        public: true

      - name: proficiency_level
        sql: proficiency_level
        type: string
        public: true

      - name: is_mastery
        sql: is_mastery
        type: boolean
        public: true

    measures:
      - name: count_scores
        description: >-
          Total number of assessment score records (one per student x assessment
          administration).
        sql: assessment_score_key
        type: count_distinct
        public: true

      - name: count_mastery
        description: >-
          Number of score records where the student met the mastery or
          proficiency threshold.
        sql: assessment_score_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_mastery = true"

      - name: pct_mastery
        description: >-
          Mastery rate — count_mastery / count_scores. Excludes NULL is_mastery
          rows (no defined threshold) from both numerator and denominator.
        sql:
          "1.0 * {count_mastery} / NULLIF({_count_scores_with_mastery_defined},
          0)"
        type: number
        format: percent
        public: true

      - name: _count_scores_with_mastery_defined
        description: >-
          Denominator for pct_mastery — score records where is_mastery is not
          NULL (i.e., a mastery threshold is defined for this assessment).
        sql: assessment_score_key
        type: count_distinct
        public: false
        filters:
          - sql: "{CUBE}.is_mastery IS NOT NULL"

      - name: count_expected
        description: >-
          Number of expected assessment takers (records in
          bridge_assessment_expectations_enrollment_scoped). NULL for state
          assessments and any administration not covered by the bridge.
        sql: assessment_expectation_key
        type: count_distinct
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/assessments/student_assessments_enrollment_scoped.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('join names:', [j['name'] for j in cube['joins']])
print('measure names:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
cube name: student_assessments_enrollment_scoped
public: False
join names: ['dates', 'assessment_administrations', 'students']
measure names: ['count_scores', 'count_mastery', 'pct_mastery', '_count_scores_with_mastery_defined', 'count_expected']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/assessments/student_assessments_enrollment_scoped.yml
git commit -m "feat(cube): add student_assessments_enrollment_scoped fact cube with bridge inlined"
```

---

## Task 3: `student_assessments_student_scoped` fact cube

Same Pattern 2 with `sql:` for bridge inline. The student-scoped bridge
(`bridge_assessment_expectations_student_scoped`) joins via
`(assessment_administration_key, student_key)` — both present on the fact. The
bridge also carries a `term_key` FK (not present on the enrollment-scoped
bridge), enabling a `terms` join for academic year / semester context on K-8
replacement-curriculum assessments.

Additional columns vs enrollment-scoped: `rank`, `max_scale_score`,
`superscore`, `running_max_scale_score` (college-entrance / AP specific — all
nullable on non-applicable rows).

Joins from this cube: `dates` (on `test_date_key`), `assessment_administrations`
(on `assessment_administration_key`), `students` (on `student_key`), `terms` (on
`b.term_key` from the inlined bridge).

`test_date_key` is nullable for AP exams (academic year recorded, no exact
date). Declare the `dates` join and accept LEFT-JOIN semantics for NULL-keyed AP
rows — AP administrations are identified via
`assessment_administrations.administration_period` (NULL) and the joined
`terms.academic_year`.

**Files:**

- Create:
  `src/cube/model/cubes/assessments/student_assessments_student_scoped.yml`

- [ ] **Step 1: Create the cube file**

Write the following as the complete content of
`src/cube/model/cubes/assessments/student_assessments_student_scoped.yml`:

```yaml
cubes:
  - name: student_assessments_student_scoped
    public: false
    sql: |
      SELECT
        f.assessment_score_key,
        f.assessment_administration_key,
        f.student_key,
        f.test_date_key,
        f.scale_score,
        f.rank,
        f.max_scale_score,
        f.superscore,
        f.running_max_scale_score,
        f.proficiency_level,
        f.is_mastery,
        b.assessment_expectation_key,
        b.term_key,
      FROM kipptaf_marts.fct_assessment_scores_student_scoped f
      LEFT JOIN kipptaf_marts.bridge_assessment_expectations_student_scoped b
        ON b.assessment_administration_key = f.assessment_administration_key
        AND b.student_key = f.student_key

    joins:
      - name: dates
        sql: >
          {dates.date_day} = CAST({CUBE}.test_date_key AS TIMESTAMP)
        relationship: many_to_one

      - name: assessment_administrations
        sql: >
          {assessment_administrations.assessment_administration_key} =
          {CUBE}.assessment_administration_key
        relationship: many_to_one

      - name: students
        sql: "{students.student_key} = {CUBE}.student_key"
        relationship: many_to_one

      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

    dimensions:
      - name: assessment_score_key
        sql: assessment_score_key
        type: string
        primary_key: true

      - name: test_date
        sql: CAST(test_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: scale_score
        sql: scale_score
        type: number
        public: true

      - name: rank
        sql: "`rank`"
        type: number
        public: true

      - name: max_scale_score
        sql: max_scale_score
        type: number
        public: true

      - name: superscore
        sql: superscore
        type: number
        public: true

      - name: running_max_scale_score
        sql: running_max_scale_score
        type: number
        public: true

      - name: proficiency_level
        sql: proficiency_level
        type: string
        public: true

      - name: is_mastery
        sql: is_mastery
        type: boolean
        public: true

    measures:
      - name: count_scores
        description: >-
          Total number of assessment score records (one per student x assessment
          administration x score type).
        sql: assessment_score_key
        type: count_distinct
        public: true

      - name: count_mastery
        description: >-
          Number of score records where the student met the mastery or
          proficiency threshold. College Board section benchmarks (EBRW, Math)
          and AP exam_score >= 3.
        sql: assessment_score_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_mastery = true"

      - name: pct_mastery
        description: >-
          Mastery rate — count_mastery / count_scores. Excludes NULL is_mastery
          rows (ACT, sub-section scores, practice rows with no defined
          benchmark) from both numerator and denominator.
        sql:
          "1.0 * {count_mastery} / NULLIF({_count_scores_with_mastery_defined},
          0)"
        type: number
        format: percent
        public: true

      - name: _count_scores_with_mastery_defined
        description: >-
          Denominator for pct_mastery — score records where is_mastery is not
          NULL.
        sql: assessment_score_key
        type: count_distinct
        public: false
        filters:
          - sql: "{CUBE}.is_mastery IS NOT NULL"

      - name: count_expected
        description: >-
          Number of expected assessment takers (records in
          bridge_assessment_expectations_student_scoped). Populated only for K-8
          replacement-curriculum assessments; NULL for college-entrance and AP
          administrations not covered by the bridge.
        sql: assessment_expectation_key
        type: count_distinct
        public: true

      - name: avg_scale_score
        description: >-
          Average scale score across all score records in the filtered set. For
          college-entrance assessments, use a filter on
          assessment_administrations.test_type or score sub-type to avoid
          averaging across incompatible score scales.
        sql: scale_score
        type: avg
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/assessments/student_assessments_student_scoped.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('join names:', [j['name'] for j in cube['joins']])
print('dimension names:', [d['name'] for d in cube['dimensions'] if not d.get('primary_key')])
print('measure names:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
cube name: student_assessments_student_scoped
public: False
join names: ['dates', 'assessment_administrations', 'students', 'terms']
dimension names: ['test_date', 'scale_score', 'rank', 'max_scale_score', 'superscore', 'running_max_scale_score', 'proficiency_level', 'is_mastery']
measure names: ['count_scores', 'count_mastery', 'pct_mastery', '_count_scores_with_mastery_defined', 'count_expected', 'avg_scale_score']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/assessments/student_assessments_student_scoped.yml
git commit -m "feat(cube): add student_assessments_student_scoped fact cube with bridge and terms inlined"
```

---

## Task 4: Enrollment-scoped detail view

Detail view: exposes individual score records including `student_key` (via
`students` join path). PII gating follows student Pattern 1 — `detail-access`
base block excludes student direct identifiers; `cube-access-student-pii`
restores full access.

Join paths:

- `student_assessments_enrollment_scoped` — fact measures + score dimensions
- `student_assessments_enrollment_scoped.dates` — date dimensions
  (`prefix: true`)
- `student_assessments_enrollment_scoped.assessment_administrations` — admin
  dimensions (`prefix: true`)
- `student_assessments_enrollment_scoped.assessment_administrations.dates` —
  administered date dimensions (`prefix: true`)
- `student_assessments_enrollment_scoped.students` — student identifiers
  (`prefix: true`)

`assessment_administrations` is not a student-domain cube (no `student_` prefix)
so its members are not stripped by `queryRewrite`. The `students` join path
members ARE stripped for users without `cube-access-student-data`.

`meta.folders` uses prefixed names for all `prefix: true` join paths. The join
path last segment is the prefix: `dates_`, `assessment_administrations_`,
`students_`. The `assessment_administrations.dates` two-hop path uses `dates_`
as its prefix (last segment is `dates`).

**Files:**

- Create:
  `src/cube/model/views/assessments/student_assessment_enrollment_scoped_detail.yml`

- [ ] **Step 1: Create the view file**

Write the following as the complete content of
`src/cube/model/views/assessments/student_assessment_enrollment_scoped_detail.yml`:

```yaml
views:
  - name: student_assessment_enrollment_scoped_detail
    description: >-
      Row-level enrollment-scoped assessment scores. One row per student x
      assessment administration. Covers internal Illuminate assessments and
      NJ/FL state assessments (NJSLA, NJGPA, FAST). Use for score drill-down,
      individual student performance, or proficiency band breakdowns. For
      aggregate mastery rates by school or grade, use
      student_assessment_enrollment_scoped_summary instead.

      is_mastery is TRUE when the student met the mastery or proficiency
      threshold for the assessment. pct_mastery counts only rows where a
      threshold is defined (is_mastery IS NOT NULL) — ACT and sub-section rows
      with no benchmark are excluded from both numerator and denominator.

      count_expected counts expected takers from the bridge table — populated
      only for Illuminate assessments with a resolvable section enrollment.
      State assessments return NULL for count_expected.

      Contains direct student identifiers — see access_policy for PII gating.

    cubes:
      - join_path: student_assessments_enrollment_scoped
        includes:
          - count_scores
          - count_mastery
          - pct_mastery
          - count_expected
          - test_date
          - scale_score
          - percent_correct
          - proficiency_level
          - is_mastery

      - join_path: student_assessments_enrollment_scoped.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_number
          - month_name

      - join_path: student_assessments_enrollment_scoped.assessment_administrations
        prefix: true
        includes:
          - administered_date
          - academic_year
          - source_project
          - administration_period
          - source_assessment_id
          - test_type

      # assessment_administrations.academic_year is exposed directly on the cube
      # (derived from administered_date_key) — no two-hop .dates join needed here.
      # A .dates join path ending in "dates" would produce the same dates_* prefix
      # as the fact's direct dates join, causing a member name collision.

      - join_path: student_assessments_enrollment_scoped.students
        prefix: true
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

    meta:
      folders:
        - name: Score
          members:
            - test_date
            - scale_score
            - percent_correct
            - proficiency_level
            - is_mastery
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_number
            - dates_month_name
        - name: Administration
          members:
            - assessment_administrations_administered_date
            - assessment_administrations_academic_year
            - assessment_administrations_academic_year
            - assessment_administrations_source_project
            - assessment_administrations_administration_period
            - assessment_administrations_source_assessment_id
            - assessment_administrations_test_type
        - name: Student
          members:
            - students_student_key
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - students_gender_identity
            - students_race
            - students_enrollment_status
            - students_is_gifted

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/assessments/student_assessment_enrollment_scoped_detail.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_assessment_enrollment_scoped_detail
join paths: ['student_assessments_enrollment_scoped', 'student_assessments_enrollment_scoped.dates', 'student_assessments_enrollment_scoped.assessment_administrations', 'student_assessments_enrollment_scoped.assessment_administrations.dates', 'student_assessments_enrollment_scoped.students']
access groups: ['detail-access', 'cube-access-student-pii']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/assessments/student_assessment_enrollment_scoped_detail.yml
git commit -m "feat(cube): add student_assessment_enrollment_scoped_detail view"
```

---

## Task 5: Enrollment-scoped summary view

Summary view: no individual identifiers. Demographic dimensions
(`gender_identity`, `race`, `is_gifted`) are retained as aggregate breakdowns.
No `student_key`, `full_name`, or direct student identifiers. `date_day` is
included so time-series trends (score trajectory by month, mastery rate by term)
work at the summary level. Single `summary-access` policy block — no `excludes`
needed.

**Files:**

- Create:
  `src/cube/model/views/assessments/student_assessment_enrollment_scoped_summary.yml`

- [ ] **Step 1: Create the view file**

Write the following as the complete content of
`src/cube/model/views/assessments/student_assessment_enrollment_scoped_summary.yml`:

```yaml
views:
  - name: student_assessment_enrollment_scoped_summary
    description: >-
      Aggregated enrollment-scoped assessment scores for mastery rate
      breakdowns. Covers internal Illuminate assessments and NJ/FL state
      assessments. No direct student identifiers — demographic dimensions (race,
      gender_identity, is_gifted) are aggregate breakdowns only.

      pct_mastery excludes NULL is_mastery rows from both numerator and
      denominator. count_expected is populated only for Illuminate assessments
      with a resolvable section enrollment.

      Use administration_administrations_administration_period and
      assessment_administrations_source_project to filter to a specific
      assessment administration cycle. For Illuminate assessments, filter on
      assessment_administrations_source_assessment_id to isolate one module
      checkpoint.

    cubes:
      - join_path: student_assessments_enrollment_scoped
        includes:
          - count_scores
          - count_mastery
          - pct_mastery
          - count_expected
          - proficiency_level
          - is_mastery

      - join_path: student_assessments_enrollment_scoped.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_number
          - month_name

      - join_path: student_assessments_enrollment_scoped.assessment_administrations
        prefix: true
        includes:
          - source_project
          - administration_period
          - source_assessment_id
          - test_type

      # assessment_administrations.academic_year is exposed directly on the cube
      # (derived from administered_date_key) — no two-hop .dates join needed here.
      # A .dates join path ending in "dates" would produce the same dates_* prefix
      # as the fact's direct dates join, causing a member name collision.

      - join_path: student_assessments_enrollment_scoped.students
        prefix: true
        includes:
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

    meta:
      folders:
        - name: Score
          members:
            - proficiency_level
            - is_mastery
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_number
            - dates_month_name
        - name: Administration
          members:
            - assessment_administrations_academic_year
            - assessment_administrations_source_project
            - assessment_administrations_administration_period
            - assessment_administrations_source_assessment_id
            - assessment_administrations_test_type
        - name: Student
          members:
            - students_gender_identity
            - students_race
            - students_enrollment_status
            - students_is_gifted

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, etc.) are
      # aggregate breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/assessments/student_assessment_enrollment_scoped_summary.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_assessment_enrollment_scoped_summary
join paths: ['student_assessments_enrollment_scoped', 'student_assessments_enrollment_scoped.dates', 'student_assessments_enrollment_scoped.assessment_administrations', 'student_assessments_enrollment_scoped.assessment_administrations.dates', 'student_assessments_enrollment_scoped.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/assessments/student_assessment_enrollment_scoped_summary.yml
git commit -m "feat(cube): add student_assessment_enrollment_scoped_summary view"
```

---

## Task 6: Student-scoped detail view

Detail view for the student-scoped fact (college-entrance and AP assessments).
Covers additional score dimensions not present in the enrollment-scoped cube:
`rank`, `max_scale_score`, `superscore`, `running_max_scale_score`. The `terms`
join path is available because the bridge carries a `term_key` — include
`academic_year` and `semester` from terms for AP and K-8 replacement-curriculum
context.

The `avg_scale_score` measure is meaningful here for college-entrance
assessments where score scales are comparable across administrations; analysts
must filter on `test_type` or `administration_period` to avoid averaging across
incompatible score types.

PII gating follows the same student Pattern 1 as the enrollment-scoped detail
view.

**Files:**

- Create:
  `src/cube/model/views/assessments/student_assessment_student_scoped_detail.yml`

- [ ] **Step 1: Create the view file**

Write the following as the complete content of
`src/cube/model/views/assessments/student_assessment_student_scoped_detail.yml`:

```yaml
views:
  - name: student_assessment_student_scoped_detail
    description: >-
      Row-level student-scoped assessment scores. One row per student x
      assessment administration x score type. Covers college-entrance
      assessments (SAT, ACT, PSAT) and AP exams. These assessments follow the
      student directly without enrollment context.

      rank is 1 for the student's best score within each assessment type.
      superscore is the best combined score across sections and administrations.
      running_max_scale_score is the running maximum up to each test date.

      is_mastery covers College Board section benchmarks (EBRW, Math) and
      Combined College-Ready totals for SAT / PSAT 8/9 / PSAT10 / NMSQT; AP:
      exam_score >= 3. NULL for ACT, sub-section scores, and practice rows with
      no defined benchmark.

      test_date_key is NULL for AP exams — use terms_academic_year or
      assessment_administrations_administration_period for AP temporal context.
      For avg_scale_score, filter on assessment_administrations test_type and
      administration_period to avoid averaging across incompatible score scales.

      Contains direct student identifiers — see access_policy for PII gating.

    cubes:
      - join_path: student_assessments_student_scoped
        includes:
          - count_scores
          - count_mastery
          - pct_mastery
          - count_expected
          - avg_scale_score
          - test_date
          - scale_score
          - rank
          - max_scale_score
          - superscore
          - running_max_scale_score
          - proficiency_level
          - is_mastery

      - join_path: student_assessments_student_scoped.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_number
          - month_name

      - join_path: student_assessments_student_scoped.assessment_administrations
        prefix: true
        includes:
          - administered_date
          - academic_year
          - source_project
          - administration_period
          - source_assessment_id
          - test_type

      - join_path: student_assessments_student_scoped.assessment_administrations.dates
        prefix: true
        includes:
          - academic_year

      - join_path: student_assessments_student_scoped.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code

      - join_path: student_assessments_student_scoped.students
        prefix: true
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

    meta:
      folders:
        - name: Score
          members:
            - test_date
            - scale_score
            - rank
            - max_scale_score
            - superscore
            - running_max_scale_score
            - proficiency_level
            - is_mastery
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_number
            - dates_month_name
        - name: Term
          members:
            - terms_academic_year
            - terms_semester
            - terms_term_name
            - terms_term_code
        - name: Administration
          members:
            - assessment_administrations_administered_date
            - assessment_administrations_academic_year
            - assessment_administrations_academic_year
            - assessment_administrations_source_project
            - assessment_administrations_administration_period
            - assessment_administrations_source_assessment_id
            - assessment_administrations_test_type
        - name: Student
          members:
            - students_student_key
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - students_gender_identity
            - students_race
            - students_enrollment_status
            - students_is_gifted

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/assessments/student_assessment_student_scoped_detail.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_assessment_student_scoped_detail
join paths: ['student_assessments_student_scoped', 'student_assessments_student_scoped.dates', 'student_assessments_student_scoped.assessment_administrations', 'student_assessments_student_scoped.assessment_administrations.dates', 'student_assessments_student_scoped.terms', 'student_assessments_student_scoped.students']
access groups: ['detail-access', 'cube-access-student-pii']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/assessments/student_assessment_student_scoped_detail.yml
git commit -m "feat(cube): add student_assessment_student_scoped_detail view"
```

---

## Task 7: Student-scoped summary view

Summary view with no direct student identifiers. Includes `avg_scale_score` and
`terms` join path for AP academic year / semester breakdowns. Demographic
dimensions retained as aggregate breakdowns. Single `summary-access` policy
block.

**Files:**

- Create:
  `src/cube/model/views/assessments/student_assessment_student_scoped_summary.yml`

- [ ] **Step 1: Create the view file**

Write the following as the complete content of
`src/cube/model/views/assessments/student_assessment_student_scoped_summary.yml`:

```yaml
views:
  - name: student_assessment_student_scoped_summary
    description: >-
      Aggregated student-scoped assessment scores for college-entrance (SAT,
      ACT, PSAT) and AP exam performance breakdowns. No direct student
      identifiers — demographic dimensions (race, gender_identity, is_gifted)
      are aggregate breakdowns only.

      pct_mastery excludes NULL is_mastery rows from both numerator and
      denominator. avg_scale_score averages across all score records in the
      filtered set — filter on assessment_administrations_test_type and
      administration_period to avoid averaging across incompatible score scales.

      For AP assessments, test_date_key is NULL. Use terms_academic_year or
      assessment_administrations_administration_period for AP temporal context.

    cubes:
      - join_path: student_assessments_student_scoped
        includes:
          - count_scores
          - count_mastery
          - pct_mastery
          - count_expected
          - avg_scale_score
          - proficiency_level
          - is_mastery

      - join_path: student_assessments_student_scoped.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_number
          - month_name

      - join_path: student_assessments_student_scoped.assessment_administrations
        prefix: true
        includes:
          - source_project
          - administration_period
          - source_assessment_id
          - test_type

      - join_path: student_assessments_student_scoped.assessment_administrations.dates
        prefix: true
        includes:
          - academic_year

      - join_path: student_assessments_student_scoped.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code

      - join_path: student_assessments_student_scoped.students
        prefix: true
        includes:
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

    meta:
      folders:
        - name: Score
          members:
            - proficiency_level
            - is_mastery
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_number
            - dates_month_name
        - name: Term
          members:
            - terms_academic_year
            - terms_semester
            - terms_term_name
            - terms_term_code
        - name: Administration
          members:
            - assessment_administrations_academic_year
            - assessment_administrations_source_project
            - assessment_administrations_administration_period
            - assessment_administrations_source_assessment_id
            - assessment_administrations_test_type
        - name: Student
          members:
            - students_gender_identity
            - students_race
            - students_enrollment_status
            - students_is_gifted

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, etc.) are
      # aggregate breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/assessments/student_assessment_student_scoped_summary.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_assessment_student_scoped_summary
join paths: ['student_assessments_student_scoped', 'student_assessments_student_scoped.dates', 'student_assessments_student_scoped.assessment_administrations', 'student_assessments_student_scoped.assessment_administrations.dates', 'student_assessments_student_scoped.terms', 'student_assessments_student_scoped.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/assessments/student_assessment_student_scoped_summary.yml
git commit -m "feat(cube): add student_assessment_student_scoped_summary view"
```

---

## Implementation Notes

### Bridge inline rationale

`bridge_assessment_expectations_enrollment_scoped` and
`bridge_assessment_expectations_student_scoped` are inlined into the fact cubes'
`sql:` blocks rather than declared as separate cubes. Both bridges have no
independent analytical grain — they add only `assessment_expectation_key` (used
to count expected takers) and are never queried standalone. A separate cube for
each bridge would require a Cube join declaration and would create a diamond
path risk if analysts tried to join the bridge cube independently.

### `dim_assessment_administrations` grain

The mart's final SELECT exposes only six columns:
`assessment_administration_key`, `administered_date_key`, `_dbt_source_project`,
`administration_period`, `source_assessment_id`, `test_type`. The analytical
attributes (`assessment_type`, `title`, `subject_area`, `scope`, `module_code`,
`grade_level`) are hash inputs only and are not materialized. The
`assessment_administrations` cube therefore exposes only what the mart produces.
If these analytical attributes are needed, they must first be added to the mart
SELECT in dbt before being surfaced here.

### `_dbt_source_project` aliased to `source_project`

The mart column is named `_dbt_source_project` (dbt plumbing convention).
Exposing it as-is in Cube with a leading underscore creates awkward UI labels.
It is aliased to `source_project` in the cube dimension
(`sql: _dbt_source_project`), which is the right layer for this rename.

### No `student_enrollments` join on enrollment-scoped fact

Despite the cube name, `fct_assessment_scores_enrollment_scoped` joins to
`dim_students` via `student_key`, not to `dim_student_enrollments` via
`student_enrollment_key`. The bridge carries `student_section_enrollment_key` as
its join column, but the fact itself exposes only `student_key` as the student
FK. The `students` join is therefore direct
(`students.student_key = CUBE.student_key`) with no `student_enrollments`
intermediary.

### Nullable `test_date_key` on student-scoped fact

AP exams do not capture an exact test date — only academic year is recorded. The
`dates` join on `test_date_key` produces NULL for AP rows. Analysts querying AP
performance should filter on
`assessment_administrations_administration_period IS NULL` (AP has NULL
administration_period) and use `terms_academic_year` for temporal context.

### `rank` is a BigQuery reserved word

The column `rank` on `fct_assessment_scores_student_scoped` has `quote: true` in
the dbt YAML (confirmed by the dbt properties file). The Cube dimension SQL
references it as `` `rank` `` (backtick-quoted) to avoid BigQuery parse errors.

### Administered-date `academic_year` on `assessment_administrations` cube

The administered-date academic year is derived directly on the
`assessment_administrations` cube (`academic_year` dimension, July-start
convention) rather than through a two-hop `assessment_administrations.dates`
join path. The reason: both the fact's direct `.dates` join path and any
`assessment_administrations.dates` two-hop path end in the segment `dates`, so
`prefix: true` on both would produce `dates_academic_year` — a member name
collision that Cube rejects at schema load.

By computing it on the cube itself, it is exposed as
`assessment_administrations_academic_year` (prefixed by the last join path
segment, `assessment_administrations`), which is distinct from the test-date
`dates_academic_year`. Analysts querying state assessments where `test_date_key`
is NULL should use `assessment_administrations_academic_year` for temporal
context.

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode. Add
the branch by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_assessment_enrollment_scoped_summary.count_scores"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string containing `fct_assessment_scores_enrollment_scoped` as a
FROM source and `bridge_assessment_expectations_enrollment_scoped` as a LEFT
JOIN.

**Check 2 — All four views appear in meta:**

```bash
curl -s "<DEV_MODE_URL>/cubejs-api/v1/meta" \
  -H "Authorization: <JWT>" \
  | jq '[.cubes[].name] | map(select(startswith("student_assessment")))'
```

Expected:
`["student_assessment_enrollment_scoped_detail", "student_assessment_enrollment_scoped_summary", "student_assessment_student_scoped_detail", "student_assessment_student_scoped_summary"]`

**Check 3 — `queryRewrite` strips assessment dimensions for users without
`cube-access-student-data`:**

Compile a query as a user with no student access — dimensions should be
stripped:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-no-student-access>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_assessment_enrollment_scoped_summary.count_scores"],"limit":1}}' \
  | jq '.sql' | grep -c "1 = 0"
```

Expected: `1` (default-deny WHERE clause because user has no scope group, and
student members stripped because no `cube-access-student-data`).

**Check 4 — PII exclusion in detail view:**

Compile a query requesting `students_full_name` as a user with `detail-access`
but without `cube-access-student-pii` — the field should be absent from the
compiled SQL:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-detail-no-pii>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["student_assessment_enrollment_scoped_detail.students_full_name"],"limit":1}}' \
  | jq '.'
```

Expected: a 500 with "You requested hidden member" — confirming the access
policy `excludes` blocks the field for users without `cube-access-student-pii`.
