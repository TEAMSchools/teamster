# Cube Surveys Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the surveys domain in the Cube semantic layer — cubes for
`fct_survey_submissions` (Pattern 2 fact) and `bridge_survey_expectations`
(separate grain), plus the `staff_survey_subject` role alias cube and four views
covering staff, student, and family respondent analytics.

**Prerequisite:** The Staff Core plan must be complete before this plan runs.
`staff_survey_subject` extends the `staff` cube — the `staff` cube must exist at
`cubes/staff/staff.yml` before `staff_survey_subject.yml` can load. Check that
`cubes/staff/staff.yml` exists before starting Task 2.

**Architecture:** All changes are in `src/cube/`. Five cube files and four view
files are created. No dbt or Dagster changes required — all source tables are
production `kipptaf_marts` views.

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Task 1: Schema validation test

Establishes the pass/fail criterion for the surveys domain. Will initially fail
on the missing files and pass once all cubes are written with correct names.
Extends the project-wide `test_cube_schema.py` with a surveys-specific check.

**Files:**

- Create: `tests/cube/test_surveys_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cube/test_surveys_schema.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CUBE_MODEL_DIR = Path(__file__).resolve().parents[2] / "src" / "cube" / "model"
SURVEYS_CUBE_DIR = CUBE_MODEL_DIR / "cubes" / "surveys"
SURVEYS_VIEW_DIR = CUBE_MODEL_DIR / "views" / "surveys"

EXPECTED_CUBE_FILES = {
    "surveys.yml",
    "survey_expectations.yml",
    "staff_survey_subject.yml",
    "survey_administrations.yml",
    "student_contact_persons.yml",
}

EXPECTED_VIEW_FILES = {
    "staff_survey_detail.yml",
    "staff_survey_summary.yml",
    "student_survey_detail.yml",
    "student_survey_summary.yml",
}


def test_surveys_cube_directory_exists() -> None:
    assert SURVEYS_CUBE_DIR.exists(), "cubes/surveys/ directory is missing"


def test_surveys_view_directory_exists() -> None:
    assert SURVEYS_VIEW_DIR.exists(), "views/surveys/ directory is missing"


@pytest.mark.parametrize("filename", sorted(EXPECTED_CUBE_FILES))
def test_surveys_cube_file_exists(filename: str) -> None:
    assert (SURVEYS_CUBE_DIR / filename).exists(), (
        f"cubes/surveys/{filename} is missing"
    )


@pytest.mark.parametrize("filename", sorted(EXPECTED_VIEW_FILES))
def test_surveys_view_file_exists(filename: str) -> None:
    assert (SURVEYS_VIEW_DIR / filename).exists(), (
        f"views/surveys/{filename} is missing"
    )


@pytest.mark.parametrize(
    "yaml_file",
    list(SURVEYS_CUBE_DIR.glob("*.yml")) if SURVEYS_CUBE_DIR.exists() else [],
    ids=lambda p: p.name,
)
def test_surveys_cubes_are_private(yaml_file: Path) -> None:
    """All survey cubes must declare public: false at the cube level."""
    data = yaml.safe_load(yaml_file.read_text())
    for cube in data.get("cubes", []):
        assert cube.get("public") is False, (
            f"{yaml_file.name}: cube '{cube['name']}' missing public: false"
        )


@pytest.mark.parametrize(
    "yaml_file",
    list(SURVEYS_CUBE_DIR.glob("*.yml")) if SURVEYS_CUBE_DIR.exists() else [],
    ids=lambda p: p.name,
)
def test_surveys_cubes_no_dim_fct_prefix(yaml_file: Path) -> None:
    """Cube names must not start with dim_ or fct_."""
    data = yaml.safe_load(yaml_file.read_text())
    for cube in data.get("cubes", []):
        name = cube["name"]
        assert not name.startswith("dim_"), (
            f"{yaml_file.name}: cube '{name}' uses reserved dim_ prefix"
        )
        assert not name.startswith("fct_"), (
            f"{yaml_file.name}: cube '{name}' uses reserved fct_ prefix"
        )
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/cube/test_surveys_schema.py -v
```

Expected: multiple FAILs — directory missing, files missing.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/cube/test_surveys_schema.py
git commit -m "test(cube): add surveys schema validation tests"
```

---

## Task 2: `staff_survey_subject` role alias cube

Creates the `staff_survey_subject` extends-alias so `surveys` can declare a
second join to `staff` for the manager-being-evaluated FK. Must come before
`surveys.yml` since Cube resolves `extends:` at schema load time.

**Why `staff_survey_subject`, not `subject_staff`:** `queryRewrite` in `cube.js`
uses `isStaffMember(m)` which checks `m.startsWith("staff")`. A cube named
`subject_staff` would not match and would bypass the staff security filter
entirely. All role alias cubes must follow the `staff_<role>` naming convention.

**Prerequisite check:** Verify `cubes/staff/staff.yml` exists before writing
this file.

```bash
ls src/cube/model/cubes/staff/staff.yml
```

If the file is absent, stop and wait for the Staff Core plan to complete.

**Files:**

- Create: `src/cube/model/cubes/surveys/staff_survey_subject.yml`

- [ ] **Step 1: Create the cube directory**

```bash
mkdir -p src/cube/model/cubes/surveys
```

- [ ] **Step 2: Write `staff_survey_subject.yml`**

```yaml
cubes:
  - name: staff_survey_subject
    # Role alias for the manager being evaluated in Manager Surveys.
    # Extends staff — inherits all dimensions without redeclaring them.
    # Named staff_survey_subject (not subject_staff) so isStaffMember() in
    # cube.js correctly gates it behind cube-access-staff-data.
    # public: false — exposed only through views via join_path traversal.
    extends: staff
    public: false
```

- [ ] **Step 3: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/surveys/staff_survey_subject.yml').read_text()
)
print('cube name:', data['cubes'][0]['name'])
print('extends:', data['cubes'][0].get('extends'))
print('public:', data['cubes'][0].get('public'))
"
```

Expected:

```text
cube name: staff_survey_subject
extends: staff
public: False
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/surveys/staff_survey_subject.yml
git commit -m "feat(cube): add staff_survey_subject role alias cube (extends staff)"
```

---

## Task 3: `surveys` cube

Maps to `fct_survey_submissions`. Pattern 2 (fact-based domain cube). Uses
`sql:` (not `sql_table:`) because `dim_survey_questions` must be inlined — it
has no independent analytical grain (its grain is question `shortname`, useful
only as an attribute of a submission row).

**Respondent FK design:** All three respondent FK columns are nullable (only one
is populated per row based on `respondent_type`). Cube declares all three joins;
at query time only the populated FK resolves to a row — the others return NULL
via the equi-join condition. This is the correct pattern: do not use a
CASE-based union join or filter to a single respondent type at the cube level.

**subject FK design:** `subject_staff_key` is the second role-playing FK to
`dim_staff`. Cube `joins:` declares it against `staff_survey_subject` (the
extends alias from Task 2), not `staff` directly.

**`dim_survey_administrations` join:** Joins via `survey_administration_key` to
expose `academic_year`, `response_deadline_date`, and `status` from the
administration dimension. `terms` is reached through `survey_administrations` —
do not add a direct `terms` join alongside it (diamond path).

**`timestamp` column:** BigQuery reserved word — needs backtick in SQL and is
cast to TIMESTAMP for the Cube time dimension.

**Note on `dim_student_contact_persons`:** The `family` respondent path joins
via `student_contact_person_key`. `dim_student_contact_persons` carries PII
columns (`full_name`, `phone`, `email`, `home_address`). These are tagged
`meta: {pii: true}` in the cube dimensions and excluded from family-respondent
views for users without `cube-access-student-pii` (family contacts are covered
by FERPA as parent/guardian information linked to a student).

**Files:**

- Create: `src/cube/model/cubes/surveys/surveys.yml`

- [ ] **Step 1: Write `surveys.yml`**

```yaml
cubes:
  - name: surveys
    public: false
    # Uses sql: (not sql_table:) to inline dim_survey_questions.
    # dim_survey_questions has no independent grain — its shortname/text/type
    # are attributes of the submission row, not a separately queryable entity.
    # All columns enumerated explicitly — no wildcard aliases.
    sql: |
      SELECT
        f.survey_submission_key,
        f.survey_administration_key,
        f.date_submitted_key,
        f.respondent_type,
        f.staff_key,
        f.student_enrollment_key,
        f.student_contact_person_key,
        f.subject_staff_key,
        f.academic_year,
        f.`timestamp`,
        q.shortname             AS question_shortname,
        q.`text`                AS question_text,
        q.`type`                AS question_type
      FROM kipptaf_marts.fct_survey_submissions f
      LEFT JOIN kipptaf_marts.dim_survey_questions q
        ON q.survey_question_key = f.survey_submission_key

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.date_submitted_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: survey_administrations
        sql: >
          {survey_administrations.survey_administration_key} =
          {CUBE}.survey_administration_key
        relationship: many_to_one

      # Respondent FK joins — only one FK is populated per row based on
      # respondent_type. All three joins are declared; non-matching rows
      # resolve to NULL via the equi-join condition. Do not filter to a single
      # respondent type at the cube level.
      - name: staff
        sql: "{staff.staff_key} = {CUBE}.staff_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      - name: student_contact_persons
        sql: >
          {student_contact_persons.student_contact_person_key} =
          {CUBE}.student_contact_person_key
        relationship: many_to_one

      # Role-playing FK: subject_staff_key → dim_staff for the manager being
      # evaluated in Manager Survey submissions. Uses the staff_survey_subject
      # extends-alias so Cube can declare two distinct joins to the same
      # underlying dim_staff table. staff_survey_subject must start with
      # "staff_" so isStaffMember() gates it correctly.
      - name: staff_survey_subject
        sql: >
          {staff_survey_subject.staff_key} = {CUBE}.subject_staff_key
        relationship: many_to_one

    dimensions:
      - name: survey_submission_key
        sql: survey_submission_key
        type: string
        primary_key: true

      - name: survey_administration_key
        sql: survey_administration_key
        type: string

      - name: respondent_type
        sql: respondent_type
        type: string
        public: true

      # Respondent FK columns — all PII per spec (role-playing identity FKs).
      - name: staff_key
        sql: staff_key
        type: string
        public: true
        meta:
          pii: true

      - name: student_enrollment_key
        sql: student_enrollment_key
        type: string
        public: true
        meta:
          pii: true

      - name: student_contact_person_key
        sql: student_contact_person_key
        type: string
        public: true
        meta:
          pii: true

      - name: subject_staff_key
        sql: subject_staff_key
        type: string
        public: true
        meta:
          pii: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: date_submitted
        sql: "CAST({CUBE}.date_submitted_key AS TIMESTAMP)"
        type: time
        public: true

      - name: submitted_at
        sql: "CAST({CUBE}.`timestamp` AS TIMESTAMP)"
        type: time
        public: true

      # Inlined from dim_survey_questions — no independent grain.
      - name: question_shortname
        sql: question_shortname
        type: string
        public: true

      - name: question_text
        sql: question_text
        type: string
        public: true

      - name: question_type
        sql: question_type
        type: string
        public: true

    measures:
      - name: count_submissions
        description: Count of distinct survey submissions.
        sql: survey_submission_key
        type: count_distinct
        public: true

      - name: count_staff_respondents
        description: Count of distinct staff respondents.
        sql: staff_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.respondent_type = 'staff'"

      - name: count_student_respondents
        description: Count of distinct student-enrollment respondents.
        sql: student_enrollment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.respondent_type = 'student'"

      - name: count_family_respondents
        description: Count of distinct family respondents.
        sql: student_contact_person_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.respondent_type = 'family'"
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/surveys/surveys.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('joins:', [j['name'] for j in cube.get('joins', [])])
print('dimensions:', [d['name'] for d in cube.get('dimensions', [])])
print('measures:', [m['name'] for m in cube.get('measures', [])])
"
```

Expected:

```text
cube name: surveys
public: False
joins: ['dates', 'survey_administrations', 'staff', 'student_enrollments', 'student_contact_persons', 'staff_survey_subject']
dimensions: ['survey_submission_key', 'survey_administration_key', 'respondent_type', 'staff_key', 'student_enrollment_key', 'student_contact_person_key', 'subject_staff_key', 'academic_year', 'date_submitted', 'submitted_at', 'question_shortname', 'question_text', 'question_type']
measures: ['count_submissions', 'count_staff_respondents', 'count_student_respondents', 'count_family_respondents']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/surveys/surveys.yml
git commit -m "feat(cube): add surveys cube (fct_survey_submissions + inlined dim_survey_questions)"
```

---

## Task 4: `survey_administrations` cube

Maps to `dim_survey_administrations`. Separate cube because `surveys` declares a
join to it and Cube must know its primary key. `dim_survey_questions` is inlined
into `surveys`; this administration dim is NOT inlined because
`bridge_survey_expectations` also joins it (two fact-side cubes share this dim —
it must stand alone).

**Files:**

- Create: `src/cube/model/cubes/surveys/survey_administrations.yml`

- [ ] **Step 1: Write `survey_administrations.yml`**

```yaml
cubes:
  - name: survey_administrations
    public: false
    sql_table: kipptaf_marts.dim_survey_administrations

    joins:
      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

    dimensions:
      - name: survey_administration_key
        sql: survey_administration_key
        type: string
        primary_key: true

      - name: survey_key
        sql: survey_key
        type: string

      - name: term_key
        sql: term_key
        type: string

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: response_deadline_date
        sql: CAST(response_deadline_date AS TIMESTAMP)
        type: time
        public: true

      - name: status
        sql: status
        type: string
        public: true
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/surveys/survey_administrations.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('joins:', [j['name'] for j in cube.get('joins', [])])
"
```

Expected:

```text
cube name: survey_administrations
public: False
joins: ['terms']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/surveys/survey_administrations.yml
git commit -m "feat(cube): add survey_administrations cube (dim_survey_administrations)"
```

---

## Task 5: `survey_expectations` cube

Maps to `bridge_survey_expectations`. **Separate cube file** — different grain
from `surveys` (one row per expected respondent × administration vs one row per
submission). Inlining it into `surveys` would produce a fanout. The bridge is
its own cube joined to `surveys` via LEFT JOIN for completion-rate analysis.

**Grain:** One row per (`survey_expectation_key` = `survey_administration_key` +
`respondent_type`

- one of the three respondent FK columns). An expected respondent may have zero
  matching submissions (intentional — completion-rate analysis needs the
  expected-but-not-submitted rows).

**Completion rate measure:** `pct_completed` is
`COUNT(DISTINCT survey_submission_key from surveys) / COUNT(survey_expectation_key)`.
The subquery pattern won't work across cubes; instead the LEFT JOIN from
`survey_expectations` to `surveys` surfaces the submission key as NULL when not
matched. `count_expected` counts all expectation rows; `count_completed` counts
only those where the join to `surveys` resolved (non-null
`survey_submission_key`). The ratio is the completion rate.

**Note on LEFT JOIN:** `survey_expectations` declares the join to `surveys`
because it is the "outer" table (every expectation row stays, matched
submissions attach). This is the reverse of a typical fact→dim join.

**Files:**

- Create: `src/cube/model/cubes/surveys/survey_expectations.yml`

- [ ] **Step 1: Write `survey_expectations.yml`**

```yaml
cubes:
  - name: survey_expectations
    public: false
    sql_table: kipptaf_marts.bridge_survey_expectations

    joins:
      - name: survey_administrations
        sql: >
          {survey_administrations.survey_administration_key} =
          {CUBE}.survey_administration_key
        relationship: many_to_one

      # LEFT JOIN to fct_survey_submissions — an expected respondent may have
      # zero matching submissions. The join is declared here (not on surveys)
      # because survey_expectations is the outer table for completion-rate
      # analysis: every expectation row is preserved; matched submission keys
      # attach where they exist.
      - name: surveys
        sql: >
          {surveys.survey_administration_key} = {CUBE}.survey_administration_key
          AND (
            ({surveys.respondent_type} = 'staff'
              AND {surveys.staff_key} = {CUBE}.staff_key)
            OR ({surveys.respondent_type} = 'student'
              AND {surveys.student_enrollment_key} =
                {CUBE}.student_enrollment_key)
            OR ({surveys.respondent_type} = 'family'
              AND {surveys.student_contact_person_key} =
                {CUBE}.student_contact_person_key)
          )
        relationship: one_to_many

      # Respondent FK joins — same pattern as surveys cube. Only one is
      # populated per row based on respondent_type.
      - name: staff
        sql: "{staff.staff_key} = {CUBE}.staff_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

    dimensions:
      - name: survey_expectation_key
        sql: survey_expectation_key
        type: string
        primary_key: true

      - name: survey_administration_key
        sql: survey_administration_key
        type: string

      - name: respondent_type
        sql: respondent_type
        type: string
        public: true

      # Respondent FK columns — PII per spec.
      - name: staff_key
        sql: staff_key
        type: string
        public: true
        meta:
          pii: true

      - name: student_enrollment_key
        sql: student_enrollment_key
        type: string
        public: true
        meta:
          pii: true

      - name: student_contact_person_key
        sql: student_contact_person_key
        type: string
        public: true
        meta:
          pii: true

    measures:
      - name: count_expected
        description: Total number of expected survey respondents.
        sql: survey_expectation_key
        type: count_distinct
        public: true

      - name: count_completed
        description: >-
          Number of expected respondents who submitted a response. Requires the
          LEFT JOIN to surveys to be active — always pair with
          survey_administrations grouping to avoid row fanout.
        sql: "{surveys.survey_submission_key}"
        type: count_distinct
        public: true

      - name: _sum_expected
        sql: "1"
        type: sum
        public: false

      - name: pct_completed
        description: >-
          Completion rate — count_completed / count_expected. Null when no
          expected respondents exist for the filter slice.
        sql: >
          {count_completed} / NULLIF({count_expected}, 0)
        type: number
        format: percent
        public: true
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/surveys/survey_expectations.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('joins:', [j['name'] for j in cube.get('joins', [])])
print('measures:', [m['name'] for m in cube.get('measures', [])])
"
```

Expected:

```text
cube name: survey_expectations
public: False
joins: ['survey_administrations', 'surveys', 'staff', 'student_enrollments']
measures: ['count_expected', 'count_completed', '_sum_expected', 'pct_completed']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/surveys/survey_expectations.yml
git commit -m "feat(cube): add survey_expectations cube (bridge_survey_expectations, separate grain)"
```

---

## Task 6: `student_contact_persons` cube

Maps to `dim_student_contact_persons`. Required as a join target for the
family-respondent path. All four non-key columns are PII (name, phone, email,
home address) — all tagged `meta: {pii: true}`. The cube is placed in the
`surveys/` folder since it is only used by the surveys domain.

**Naming:** `student_contact_persons` (not `dim_student_contact_persons`) per
the naming convention. Must start with `student_` so `isStudentMember()` in
`cube.js` gates it behind `cube-access-student-data`.

**Files:**

- Create: `src/cube/model/cubes/surveys/student_contact_persons.yml`

- [ ] **Step 1: Write `student_contact_persons.yml`**

```yaml
cubes:
  - name: student_contact_persons
    public: false
    sql_table: kipptaf_marts.dim_student_contact_persons

    dimensions:
      - name: student_contact_person_key
        sql: student_contact_person_key
        type: string
        primary_key: true

      # All four non-key columns are direct identifiers — PII per FERPA
      # (parent/guardian contact information linked to a student).
      - name: full_name
        sql: full_name
        type: string
        public: true
        meta:
          pii: true

      - name: phone
        sql: phone
        type: string
        public: true
        meta:
          pii: true

      - name: email
        sql: email
        type: string
        public: true
        meta:
          pii: true

      - name: home_address
        sql: home_address
        type: string
        public: true
        meta:
          pii: true
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/surveys/student_contact_persons.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('pii dims:', [d['name'] for d in cube['dimensions'] if d.get('meta', {}).get('pii')])
"
```

Expected:

```text
cube name: student_contact_persons
public: False
pii dims: ['full_name', 'phone', 'email', 'home_address']
```

- [ ] **Step 3: Run surveys schema tests — file-existence tests should now
      pass**

```bash
uv run pytest tests/cube/test_surveys_schema.py -v
```

Expected: all five cube-file existence tests PASS; view-file existence tests
still FAIL.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/surveys/student_contact_persons.yml
git commit -m "feat(cube): add student_contact_persons cube (dim_student_contact_persons, surveys domain)"
```

---

## Task 7: Staff survey views

Two views for the staff-respondent slice of surveys. Staff surveys include the
Manager Survey subtype where `subject_staff_key` is populated. Both views expose
the `staff_survey_subject` join path so subject dimensions are accessible.

**Access policy design:**

- `staff_survey_detail`: `detail-access` base block with PII excludes for both
  the respondent (`staff_*` prefixed fields from the `staff` join path) and the
  subject (`staff_survey_subject_*` prefixed fields from the
  `staff_survey_subject` join path). `cube-access-staff-pii` restores full
  access.
- `staff_survey_summary`: `summary-access` only — no individual identifiers, no
  PII tier needed.

**`prefix: true` and PII field names:** When `prefix: true` is set on a join
path, the last segment of `join_path` is prepended to every field.
`join_path: surveys.staff` with `prefix: true` → fields become `staff_*`.
`join_path: surveys.staff_survey_subject` with `prefix: true` → fields become
`staff_survey_subject_*`. The `excludes:` list in `access_policy` must use the
post-prefix names.

**Files:**

- Create: `src/cube/model/views/surveys/staff_survey_detail.yml`
- Create: `src/cube/model/views/surveys/staff_survey_summary.yml`

- [ ] **Step 1: Create the views directory**

```bash
mkdir -p src/cube/model/views/surveys
```

- [ ] **Step 2: Write `staff_survey_detail.yml`**

```yaml
views:
  - name: staff_survey_detail
    description: >-
      Row-level staff survey submissions. One row per staff respondent x survey
      administration. Includes Manager Survey submissions where
      subject_staff_key is populated (the manager being evaluated).
      respondent_type is always 'staff' in this view — filter applied at query
      time via the join to the surveys cube. For completion-rate analysis, use
      staff_survey_summary which joins survey_expectations. Contains direct
      staff identifiers for both respondent and subject — see access_policy for
      PII gating.

    cubes:
      - join_path: surveys
        includes:
          - count_submissions
          - count_staff_respondents
          - respondent_type
          - date_submitted
          - submitted_at
          - academic_year
          - question_shortname
          - question_text
          - question_type

      - join_path: surveys.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: surveys.survey_administrations
        prefix: true
        includes:
          - academic_year
          - response_deadline_date
          - status

      - join_path: surveys.survey_administrations.terms
        prefix: true
        includes:
          - term_name
          - term_code
          - semester

      # Respondent staff — PII fields gated by cube-access-staff-pii.
      - join_path: surveys.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - google_email
          - gender_identity
          - race
          - is_hispanic

      # Subject staff (Manager Survey only — null for all other survey types).
      # prefix: true → fields become staff_survey_subject_*.
      - join_path: surveys.staff_survey_subject
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email

    meta:
      folders:
        - name: Submission
          members:
            - respondent_type
            - date_submitted
            - submitted_at
            - question_shortname
            - question_text
            - question_type
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
        - name: Administration
          members:
            - survey_administrations_academic_year
            - survey_administrations_response_deadline_date
            - survey_administrations_status
            - terms_term_name
            - terms_term_code
            - terms_semester
        - name: Respondent Staff
          members:
            - staff_staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
        - name: Subject Staff
          members:
            - staff_survey_subject_staff_key
            - staff_survey_subject_full_name
            - staff_survey_subject_first_name
            - staff_survey_subject_last_name
            - staff_survey_subject_work_email

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            # Respondent staff PII (prefix: staff_)
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
            # Subject staff PII (prefix: staff_survey_subject_)
            - staff_survey_subject_full_name
            - staff_survey_subject_first_name
            - staff_survey_subject_last_name
            - staff_survey_subject_work_email
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 3: Write `staff_survey_summary.yml`**

```yaml
views:
  - name: staff_survey_summary
    description: >-
      Aggregated staff survey submissions and completion rates. No individual
      staff identifiers — demographic breakdowns (gender, race) only. For
      completion-rate analysis, dimensions from survey_expectations are surfaced
      alongside submission counts. Pair count_submissions with count_expected to
      compute pct_completed; do not average the per-row ratio.

    cubes:
      - join_path: surveys
        includes:
          - count_submissions
          - count_staff_respondents
          - respondent_type
          - academic_year
          - question_shortname
          - question_type

      - join_path: surveys.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: surveys.survey_administrations
        prefix: true
        includes:
          - academic_year
          - status

      - join_path: surveys.survey_administrations.terms
        prefix: true
        includes:
          - term_name
          - semester

      # Aggregate demographic breakdowns — no individual identifiers.
      - join_path: surveys.staff
        prefix: true
        includes:
          - gender_identity
          - race
          - is_hispanic

    access_policy:
      # No PII tier — view contains no direct staff identifiers.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 4: Verify both YAML files parse**

```bash
uv run python -c "
import yaml
from pathlib import Path

for fname in ['staff_survey_detail.yml', 'staff_survey_summary.yml']:
    data = yaml.safe_load(
        (Path('src/cube/model/views/surveys') / fname).read_text()
    )
    view = data['views'][0]
    print(fname)
    print('  view name:', view['name'])
    print('  join paths:', [c['join_path'] for c in view['cubes']])
    print('  access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected:

```text
staff_survey_detail.yml
  view name: staff_survey_detail
  join paths: ['surveys', 'surveys.dates', 'surveys.survey_administrations', 'surveys.survey_administrations.terms', 'surveys.staff', 'surveys.staff_survey_subject']
  access groups: ['detail-access', 'cube-access-staff-pii']
staff_survey_summary.yml
  view name: staff_survey_summary
  join paths: ['surveys', 'surveys.dates', 'surveys.survey_administrations', 'surveys.survey_administrations.terms', 'surveys.staff']
  access groups: ['summary-access']
```

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/surveys/staff_survey_detail.yml \
        src/cube/model/views/surveys/staff_survey_summary.yml
git commit -m "feat(cube): add staff_survey_detail and staff_survey_summary views"
```

---

## Task 8: Student survey views

Two views for the student-respondent slice of surveys. Student surveys do not
carry `subject_staff_key` (only Manager Surveys do, which are staff→staff).
Location context is reached through `student_enrollments.locations` — do not add
a direct `locations` join to `surveys` (diamond path through
`student_enrollments`).

**Access policy design:**

- `student_survey_detail`: `detail-access` base block with student PII excludes.
  Separately, `cube-access-student-pii` restores full access. Note:
  `queryRewrite` enforces `isStudentMember` on top — a user needs both
  `cube-access-student-data` (via `queryRewrite`) AND `detail-access` (via the
  access policy) to reach this view.
- `student_survey_summary`: `summary-access` only — no individual identifiers.

**`student_enrollment_key` as PII:** The respondent FK is a surrogate but traces
directly to an individual student enrollment record. Tagged `meta: {pii: true}`
on the cube dimension; excluded from the detail view without
`cube-access-student-pii`.

**Family respondent exclusion:** Family surveys (respondent_type = 'family') are
not in these views. Contact person attributes live on `student_contact_persons`
and are exposed only if a family-survey view is added in a future task. For now,
the views are scoped to student-type respondents and consumers should filter
`respondent_type = 'student'`.

**Files:**

- Create: `src/cube/model/views/surveys/student_survey_detail.yml`
- Create: `src/cube/model/views/surveys/student_survey_summary.yml`

- [ ] **Step 1: Write `student_survey_detail.yml`**

```yaml
views:
  - name: student_survey_detail
    description: >-
      Row-level student survey submissions. One row per student-enrollment
      respondent x survey administration. respondent_type is always 'student' in
      this view — filter at query time. Location context is reached through
      student_enrollments.locations — do not add a direct locations join
      (diamond path). Contains direct student identifiers — see access_policy
      for PII gating. queryRewrite enforces cube-access-student-data membership
      independently of this access_policy.

    cubes:
      - join_path: surveys
        includes:
          - count_submissions
          - count_student_respondents
          - respondent_type
          - date_submitted
          - submitted_at
          - academic_year
          - question_shortname
          - question_text
          - question_type

      - join_path: surveys.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: surveys.survey_administrations
        prefix: true
        includes:
          - academic_year
          - response_deadline_date
          - status

      - join_path: surveys.survey_administrations.terms
        prefix: true
        includes:
          - term_name
          - term_code
          - semester

      - join_path: surveys.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year
          - entry_date
          - exit_date
          - is_retained_year

      - join_path: surveys.student_enrollments.students
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

      - join_path: surveys.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: surveys.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

    meta:
      folders:
        - name: Submission
          members:
            - respondent_type
            - date_submitted
            - submitted_at
            - question_shortname
            - question_text
            - question_type
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
        - name: Administration
          members:
            - survey_administrations_academic_year
            - survey_administrations_response_deadline_date
            - survey_administrations_status
            - terms_term_name
            - terms_term_code
            - terms_semester
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
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year
            - student_enrollments_entry_date
            - student_enrollments_exit_date
            - student_enrollments_is_retained_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - student_enrollments_student_enrollment_key
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Write `student_survey_summary.yml`**

```yaml
views:
  - name: student_survey_summary
    description: >-
      Aggregated student survey submissions. No individual student identifiers —
      demographic breakdowns (gender, race, grade level) only. For
      completion-rate analysis across student respondents, pair
      count_submissions with survey_expectations data. Omitting a
      respondent_type filter returns all respondent types; filter to 'student'
      for student-only aggregates.

    cubes:
      - join_path: surveys
        includes:
          - count_submissions
          - count_student_respondents
          - respondent_type
          - academic_year
          - question_shortname
          - question_type

      - join_path: surveys.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: surveys.survey_administrations
        prefix: true
        includes:
          - academic_year
          - status

      - join_path: surveys.survey_administrations.terms
        prefix: true
        includes:
          - term_name
          - semester

      - join_path: surveys.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year
          - is_retained_year

      - join_path: surveys.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race
          - is_gifted
          - enrollment_status

      - join_path: surveys.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: surveys.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, etc.) are aggregate
      # breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify both YAML files parse**

```bash
uv run python -c "
import yaml
from pathlib import Path

for fname in ['student_survey_detail.yml', 'student_survey_summary.yml']:
    data = yaml.safe_load(
        (Path('src/cube/model/views/surveys') / fname).read_text()
    )
    view = data['views'][0]
    print(fname)
    print('  view name:', view['name'])
    print('  join paths:', [c['join_path'] for c in view['cubes']])
    print('  access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected:

```text
student_survey_detail.yml
  view name: student_survey_detail
  join paths: ['surveys', 'surveys.dates', 'surveys.survey_administrations', 'surveys.survey_administrations.terms', 'surveys.student_enrollments', 'surveys.student_enrollments.students', 'surveys.student_enrollments.locations', 'surveys.student_enrollments.locations.regions']
  access groups: ['detail-access', 'cube-access-student-pii']
student_survey_summary.yml
  view name: student_survey_summary
  join paths: ['surveys', 'surveys.dates', 'surveys.survey_administrations', 'surveys.survey_administrations.terms', 'surveys.student_enrollments', 'surveys.student_enrollments.students', 'surveys.student_enrollments.locations', 'surveys.student_enrollments.locations.regions']
  access groups: ['summary-access']
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS including `test_surveys_schema.py`.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/surveys/student_survey_detail.yml \
        src/cube/model/views/surveys/student_survey_summary.yml
git commit -m "feat(cube): add student_survey_detail and student_survey_summary views"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode. Add
the branch by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads (staff respondents):**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["staff_survey_summary.count_submissions"],
      "dimensions": ["staff_survey_summary.respondent_type"],
      "limit": 1
    }
  }' | jq '.sql'
```

Expected: a SQL string referencing `kipptaf_marts.fct_survey_submissions`.

**Check 2 — Role alias join resolves (Manager Survey subject):**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["staff_survey_detail.count_submissions"],
      "dimensions": ["staff_survey_detail.staff_survey_subject_full_name"],
      "limit": 1
    }
  }' | jq '.sql'
```

Expected: SQL contains two joins to `kipptaf_marts.dim_staff` under different
aliases — one for the respondent FK (`staff_key`) and one for the subject FK
(`subject_staff_key`).

**Check 3 — Survey expectations completion rate:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": [
        "survey_expectations.count_expected",
        "survey_expectations.count_completed",
        "survey_expectations.pct_completed"
      ],
      "dimensions": ["survey_expectations.respondent_type"],
      "limit": 5
    }
  }' | jq '.sql'
```

Expected: SQL contains LEFT JOIN from `bridge_survey_expectations` to
`fct_survey_submissions`. `count_completed` uses the submission key;
`count_expected` uses the expectation key.

**Check 4 — `queryRewrite` strips student members for non-student-data users:**

Compile `student_survey_summary.count_submissions` with a user who has
`detail-access` but lacks `cube-access-student-data`. The SQL should contain
`WHERE (1 = 0)` (default deny from the student-member strip) or return no
student-prefixed members.

**Check 5 — Cube `meta` lists all four views:**

The Cube MCP `meta` tool (or `/v1/meta` endpoint with a network-scoped user)
should list: `staff_survey_detail`, `staff_survey_summary`,
`student_survey_detail`, `student_survey_summary`.

---

## File inventory

| File                                        | Type | dbt source                                                |
| ------------------------------------------- | ---- | --------------------------------------------------------- |
| `cubes/surveys/staff_survey_subject.yml`    | Cube | `extends: staff` (no table)                               |
| `cubes/surveys/surveys.yml`                 | Cube | `fct_survey_submissions` + inlined `dim_survey_questions` |
| `cubes/surveys/survey_administrations.yml`  | Cube | `dim_survey_administrations`                              |
| `cubes/surveys/survey_expectations.yml`     | Cube | `bridge_survey_expectations`                              |
| `cubes/surveys/student_contact_persons.yml` | Cube | `dim_student_contact_persons`                             |
| `views/surveys/staff_survey_detail.yml`     | View | (no table — selects from cubes)                           |
| `views/surveys/staff_survey_summary.yml`    | View | (no table — selects from cubes)                           |
| `views/surveys/student_survey_detail.yml`   | View | (no table — selects from cubes)                           |
| `views/surveys/student_survey_summary.yml`  | View | (no table — selects from cubes)                           |
| `tests/cube/test_surveys_schema.py`         | Test | (validates cube/view structure)                           |

## Design decisions recorded

**`dim_survey_questions` inlined:** The question dim has no independent
analytical grain — `shortname`, `text`, and `type` are attributes of the
submission row. Inlining via LEFT JOIN in the `surveys` cube `sql:` block avoids
a separate cube that would never be queried alone.

**`survey_administrations` NOT inlined:** Two fact-side cubes (`surveys` and
`survey_expectations`) both join the administration dim. It must stand alone as
a separate cube so both can declare joins to it without duplicating its columns.

**`survey_expectations` is a separate cube:** Different grain from
`fct_survey_submissions` — one row per expected respondent × administration vs
one row per submission. Inlining would produce a fanout. Completion-rate
analysis (expected vs taken) requires the LEFT JOIN pattern from
`survey_expectations` to `surveys`.

**`staff_survey_subject` naming:** Must start with `staff_` (not
`subject_staff`) so `isStaffMember()` in `cube.js` correctly gates it behind
staff access controls. See spec section on role-playing FK dimensions.

**Family respondent view deferred:** `dim_student_contact_persons` contact
attributes are fully PII-tagged and the cube is available as a join target. A
`family_survey_detail` / `family_survey_summary` view pair can be added in a
follow-up task once the access group for family-contact PII (likely
`cube-access-student-pii`) is confirmed with the team.

**No direct `locations` join on `surveys`:** Location context for
student-respondent surveys is reached through
`surveys.student_enrollments.locations` — adding a direct join alongside the
`student_enrollments` join would create a diamond path.
