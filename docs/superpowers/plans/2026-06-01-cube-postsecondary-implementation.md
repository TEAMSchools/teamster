> **Measures: not implemented in this pass.** Skip all `measures:` sections when
> writing cube files — dimensions, joins, and `public: false` only. Remove
> measure names from view `includes:` lists (keep dimension names only). Add
> measures on demand as analysts request specific aggregations.

# Cube Postsecondary (College) Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the postsecondary (college) domain in the Cube semantic
layer, covering all columns in `dim_college_enrollments`. Exposes enrollment
status, degree, major, graduation flag, withdrawal flag, and related dimensions
via a cube and two consumer-facing views.

**Prerequisite:** Plan `2026-06-01-cube-model-yaml-implementation.md` (Plan 0)
must be complete first. The student core cubes (`students` and
`student_enrollments`) must exist and use their post-rename names (without
`dim_` prefix). All steps below assume Plan 0 has run.

**Architecture:** One new cube file in `src/cube/model/cubes/students/`. Two new
view files in `src/cube/model/views/students/` (directory is new — create it).
No `cube.js` changes required — the `student_` prefix automatically triggers
`isStudentMember` in `queryRewrite`.

**Tech Stack:** Cube YAML (`src/cube/model/`), Python (YAML parse verification)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md` — "Note
on college (postsecondary) domain"

---

## Blocked Metrics

The following postsecondary metrics are **out of scope for this plan** and must
not be implemented until issue #3695 (KIPPADB/Salesforce mart models) is
resolved:

| Metric / Domain           | Blocker                                             |
| ------------------------- | --------------------------------------------------- |
| FAFSA completion          | KIPPADB Salesforce model not yet in `models/marts/` |
| FSA ID tracking           | KIPPADB Salesforce model not yet in `models/marts/` |
| HESAA aid data            | KIPPADB Salesforce model not yet in `models/marts/` |
| Application tracking      | KIPPADB Salesforce model not yet in `models/marts/` |
| ECC scores                | KIPPADB Salesforce model not yet in `models/marts/` |
| Award letters             | KIPPADB Salesforce model not yet in `models/marts/` |
| College GPA               | KIPPADB Salesforce model not yet in `models/marts/` |
| Career launch metrics     | KIPPADB Salesforce model not yet in `models/marts/` |
| Alumni contact dimensions | KIPPADB Salesforce model not yet in `models/marts/` |

Do not add stubs, placeholders, or `TODO` measures for these. Revisit after
#3695 lands.

---

## dbt Model Findings

Answers to the key questions from `dim_college_enrollments.yml`:

| Question                          | Answer                                                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Primary key column                | `college_enrollment_key` (surrogate, `generate_surrogate_key(["student_number", "college_code_branch"])`)       |
| Student FK                        | `student_key` → `dim_students` (no `student_enrollment_key`)                                                    |
| Date FKs                          | `start_date_key` (DATE, role-playing) and `end_date_key` (DATE, role-playing) — both FK to `dim_dates`          |
| Columns with `contains_pii: true` | None declared in the dbt property YAML                                                                          |
| Available measures                | Count of graduates (`is_graduated`), graduation rate, count of withdrawn, count by status, count of enrollments |

**No PII-tagged columns** in `dim_college_enrollments`. No `meta: {pii: true}`
annotations are needed on any cube dimension, and no PII `excludes` block is
required in the detail view's access policy. The detail view's access policy is
still needed to gate on `detail-access`.

**Grain note:** `dim_college_enrollments` has one row per student × college
combination across the full NSC tenure. It is not a per-term or per-year table.
`start_date_key` and `end_date_key` are role-playing FKs to `dim_dates`
(earliest and latest enrollment dates across NSC records); they are NOT used for
a date-dimension join (that would require a single equi-join date column).
Expose them as time dimensions cast to TIMESTAMP directly on the cube; do not
join `dates` here.

**Join shape:** `dim_college_enrollments` has `student_key` → `dim_students`.
There is no `student_enrollment_key`, so the join path is
`student_college_enrollments.students` — not through `student_enrollments`. This
is a direct student-level grain (one record per student × college, not per
enrollment stint).

---

## Task 1: Create the views directory

The `src/cube/model/views/students/` directory does not exist. Create it before
writing any view files.

**Files:**

- Create directory: `src/cube/model/views/students/`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p src/cube/model/views/students
```

- [ ] **Step 2: Verify**

```bash
ls src/cube/model/views/
```

Expected: `attendance` and `students` directories both present.

- [ ] **Step 3: Commit the empty directory (with a `.gitkeep`)**

```bash
touch src/cube/model/views/students/.gitkeep
git add src/cube/model/views/students/.gitkeep
git commit -m "feat(cube): create views/students directory for college and future student views"
```

---

## Task 2: Write the cube file — `student_college_enrollments.yml`

Pattern 1 (conformed dim thin wrapper) — single `sql_table:`, no joins needed.
The cube joins to `students` so the detail view can traverse via
`student_college_enrollments.students`.

**Files:**

- Create: `src/cube/model/cubes/students/student_college_enrollments.yml`

- [ ] **Step 1: Write the cube file**

Write the following as the complete content of
`src/cube/model/cubes/students/student_college_enrollments.yml`:

```yaml
cubes:
  - name: student_college_enrollments
    public: false
    sql_table: kipptaf_marts.dim_college_enrollments

    joins:
      - name: students
        sql: "{students.student_key} = {CUBE}.student_key"
        relationship: many_to_one

    dimensions:
      - name: college_enrollment_key
        sql: college_enrollment_key
        type: string
        primary_key: true

      - name: student_key
        sql: student_key
        type: string

      - name: college_key
        sql: college_key
        type: string
        public: true

      - name: enrollment_start_date
        sql: CAST(start_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: enrollment_end_date
        sql: CAST(end_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: status
        sql: status
        type: string
        public: true

      - name: degree_title
        sql: degree_title
        type: string
        public: true

      - name: major
        sql: major
        type: string
        public: true

      - name: class_level
        sql: class_level
        type: string
        public: true

      - name: is_graduated
        sql: is_graduated
        type: boolean
        public: true

      - name: is_withdrawn
        sql: is_withdrawn
        type: boolean
        public: true

      - name: count_graduates
        description: >-
          Distinct student × college combinations where the student has a
          graduated NSC record (is_graduated = true).
        sql: college_enrollment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_graduated = true"

      - name: count_withdrawn
        description: >-
          Distinct student × college combinations where the student has a
          withdrawal NSC record (is_withdrawn = true).
        sql: college_enrollment_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_withdrawn = true"

      - name: _count_enrollments_for_rate
        description: >-
          Internal denominator for graduation and withdrawal rate calculations.
          Counts all student × college combinations regardless of outcome.
        sql: college_enrollment_key
        type: count_distinct
        public: false

      - name: graduation_rate
        description: >-
          Proportion of student × college combinations that resulted in a
          graduation (is_graduated = true) out of all combinations.
          SUM(is_graduated) / COUNT(DISTINCT college_enrollment_key).
        sql: "{count_graduates} / NULLIF({_count_enrollments_for_rate}, 0)"
        type: number
        format: percent
        public: true

      - name: withdrawal_rate
        description: >-
          Proportion of student × college combinations that resulted in a
          withdrawal (is_withdrawn = true) out of all combinations.
        sql: "{count_withdrawn} / NULLIF({_count_enrollments_for_rate}, 0)"
        type: number
        format: percent
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/students/student_college_enrollments.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('sql_table:', cube.get('sql_table'))
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
cube name: student_college_enrollments
public: False
sql_table: kipptaf_marts.dim_college_enrollments
dimensions: ['college_enrollment_key', 'student_key', 'college_key', 'enrollment_start_date', 'enrollment_end_date', 'status', 'degree_title', 'major', 'class_level', 'is_graduated', 'is_withdrawn']
measures: ['count_college_enrollments', 'count_graduates', 'count_withdrawn', '_count_enrollments_for_rate', 'graduation_rate', 'withdrawal_rate']
```

- [ ] **Step 3: Run the cube schema test to confirm the new cube passes**

```bash
uv run pytest tests/cube/test_cube_schema.py -v -k student_college
```

Expected: PASS — cube name starts with `student_`, no `dim_`/`fct_` prefix.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/students/student_college_enrollments.yml
git commit -m "feat(cube): add student_college_enrollments cube — maps to dim_college_enrollments"
```

---

## Task 3: Write the detail view — `student_college_enrollments_detail.yml`

Detail view exposes individual enrollment records. The `students` join path
provides student identifiers. No PII fields in `dim_college_enrollments` itself,
but student PII from the `students` join path is gated under
`cube-access-student-pii`.

**Access policy reasoning:** No PII columns exist on `dim_college_enrollments`
(no `contains_pii: true` in the dbt property YAML). The student PII fields come
from the `students` join path (`full_name`, `birth_date`,
`lea_student_identifier`, `state_student_identifier`). These are gated exactly
as in the attendance detail view — `detail-access` excludes them;
`cube-access-student-pii` restores full access. `college_key` is a surrogate
(not a direct identifier). `major` and `degree_title` are not PII.

**Files:**

- Create: `src/cube/model/views/students/student_college_enrollments_detail.yml`

- [ ] **Step 1: Write the detail view file**

Write the following as the complete content of
`src/cube/model/views/students/student_college_enrollments_detail.yml`:

```yaml
views:
  - name: student_college_enrollments_detail
    description: >-
      Row-level postsecondary college enrollment records from the National
      Student Clearinghouse (NSC). One row per student × college combination,
      representing the full tenure across all NSC records for that pairing.
      Covers enrollment status (status code), degree title, major, class level,
      graduation flag (is_graduated), and withdrawal flag (is_withdrawn).

      Grain note: this is not a term-by-term or year-by-year table. Each row
      spans the student's full tenure at a college (earliest start_date to
      latest end_date across NSC records). enrollment_start_date and
      enrollment_end_date are the full tenure bounds, not individual term dates.

      count_graduates and graduation_rate count student × college combinations,
      not individual students. A student who graduated from two colleges counts
      twice. To count distinct students who have graduated from at least one
      college, filter is_graduated = true and count students_student_key.

      For summary-only analytics without student identifiers, use
      student_college_enrollments_summary instead.

      FAFSA, HESAA, ECC scores, application tracking, award letters, college
      GPA, and career launch metrics are not available — blocked on #3695
      (KIPPADB/Salesforce mart models).

    cubes:
      - join_path: student_college_enrollments
        includes:
          - count_college_enrollments
          - count_graduates
          - count_withdrawn
          - graduation_rate
          - withdrawal_rate
          - college_key
          - enrollment_start_date
          - enrollment_end_date
          - status
          - degree_title
          - major
          - class_level
          - is_graduated
          - is_withdrawn

      - join_path: student_college_enrollments.students
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
        - name: Enrollment
          members:
            - college_key
            - enrollment_start_date
            - enrollment_end_date
            - status
            - degree_title
            - major
            - class_level
            - is_graduated
            - is_withdrawn
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
            - students_district_student_identifier
            - students_salesforce_contact_id
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/students/student_college_enrollments_detail.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_college_enrollments_detail
join paths: ['student_college_enrollments', 'student_college_enrollments.students']
access groups: ['detail-access', 'cube-access-student-pii']
```

- [ ] **Step 3: Confirm all `public: true` members are declared on the cube**

Cross-check: every member listed under `includes:` in either join path block
must have `public: true` on the corresponding cube dimension or measure. The
checklist:

From `student_college_enrollments` (cube file, Task 2):

- `count_college_enrollments` — `public: true` ✓
- `count_graduates` — `public: true` ✓
- `count_withdrawn` — `public: true` ✓
- `graduation_rate` — `public: true` ✓
- `withdrawal_rate` — `public: true` ✓
- `college_key` — `public: true` ✓
- `enrollment_start_date` — `public: true` ✓
- `enrollment_end_date` — `public: true` ✓
- `status` — `public: true` ✓
- `degree_title` — `public: true` ✓
- `major` — `public: true` ✓
- `class_level` — `public: true` ✓
- `is_graduated` — `public: true` ✓
- `is_withdrawn` — `public: true` ✓

From `students` (existing cube, `cubes/students/students.yml`):

- `student_key` — `public: true` ✓ (primary key, confirmed in file)
- `full_name` — `public: true` ✓
- `birth_date` — `public: true` ✓ (check if present; add if missing)
- `lea_student_identifier` — `public: true` ✓
- `state_student_identifier` — `public: true` ✓
- `gender_identity` — `public: true` ✓
- `race` — `public: true` ✓
- `enrollment_status` — `public: true` ✓
- `is_gifted` — `public: true` ✓

If any member is missing `public: true` on the cube, add it to the cube file
before proceeding.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/students/student_college_enrollments_detail.yml
git commit -m "feat(cube): add student_college_enrollments_detail view — college enrollment detail with student PII gating"
```

---

## Task 4: Write the summary view — `student_college_enrollments_summary.yml`

Summary view exposes only measures and grouping dimensions. No student
identifiers. Single `summary-access` access policy block.

**Files:**

- Create:
  `src/cube/model/views/students/student_college_enrollments_summary.yml`

- [ ] **Step 1: Write the summary view file**

Write the following as the complete content of
`src/cube/model/views/students/student_college_enrollments_summary.yml`:

```yaml
views:
  - name: student_college_enrollments_summary
    description: >-
      Aggregated postsecondary college enrollment metrics from the National
      Student Clearinghouse (NSC). No direct student identifiers — demographic
      dimensions are aggregate breakdowns only. One effective row per filter
      slice of college enrollment records.

      Grain note: each underlying row is one student × college tenure. Counts
      and rates operate over student × college combinations, not individual
      students. A student who attended two colleges contributes to two rows.

      count_graduates and graduation_rate count student × college combinations
      where is_graduated = true. For drill-down or individual investigation, use
      student_college_enrollments_detail instead.

      FAFSA, HESAA, ECC scores, application tracking, award letters, college
      GPA, and career launch metrics are not available — blocked on #3695
      (KIPPADB/Salesforce mart models).

    cubes:
      - join_path: student_college_enrollments
        includes:
          - count_college_enrollments
          - count_graduates
          - count_withdrawn
          - graduation_rate
          - withdrawal_rate
          - status
          - degree_title
          - major
          - class_level
          - is_graduated
          - is_withdrawn
          - enrollment_start_date
          - enrollment_end_date

      - join_path: student_college_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

    meta:
      folders:
        - name: Enrollment
          members:
            - status
            - degree_title
            - major
            - class_level
            - is_graduated
            - is_withdrawn
            - enrollment_start_date
            - enrollment_end_date
        - name: Student
          members:
            - students_gender_identity
            - students_race
            - students_enrollment_status
            - students_is_gifted

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, etc.) are
      # aggregate breakdowns only; no student_key or name fields.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/students/student_college_enrollments_summary.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_college_enrollments_summary
join paths: ['student_college_enrollments', 'student_college_enrollments.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/students/student_college_enrollments_summary.yml
git commit -m "feat(cube): add student_college_enrollments_summary view — college enrollment summary with no student identifiers"
```

---

## Task 5: Run the full cube schema test suite

Confirm all cube files pass the naming convention test, including the new cube.

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS. The new `student_college_enrollments` cube must appear
and pass the `test_cube_name_no_dim_or_fct_prefix` check.

- [ ] **Step 2: Remove the `.gitkeep` from the views directory (if the views
      files are committed)**

```bash
git rm src/cube/model/views/students/.gitkeep
git commit -m "chore(cube): remove .gitkeep from views/students now that view files exist"
```

Skip this step if `.gitkeep` was not committed separately in Task 1 (it can be
omitted from the initial commit if both view files are ready).

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode. Dev
Mode (per-developer branch endpoint) is the only environment where server
`console.log` output is visible.

**Check 1 — Model loads (summary view):**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["student_college_enrollments_summary.count_college_enrollments"],
      "limit": 1
    }
  }' \
  | jq '.sql'
```

Expected: a SQL string containing `dim_college_enrollments` as the FROM source.

**Check 2 — Model loads (detail view):**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["student_college_enrollments_detail.count_graduates"],
      "dimensions": ["student_college_enrollments_detail.status"],
      "limit": 1
    }
  }' \
  | jq '.sql'
```

Expected: SQL containing `is_graduated = true` in the WHERE clause or FILTER()
around the count_graduates measure.

**Check 3 — Student join resolves:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-with-cube-access-student-pii>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "dimensions": [
        "student_college_enrollments_detail.students_student_key",
        "student_college_enrollments_detail.status"
      ],
      "limit": 5
    }
  }' \
  | jq '.sql'
```

Expected: SQL containing a JOIN from `dim_college_enrollments` to `dim_students`
on `student_key`.

**Check 4 — PII gate works (detail view, no PII group):**

Query for `students_full_name` with a user who has `detail-access` but not
`cube-access-student-pii`. The response should return a "hidden member" error or
empty result, confirming the `excludes` block is active.

**Check 5 — Security gate works (queryRewrite, no student-data group):**

Compile a query with a user who has a scope group but lacks
`cube-access-student-data`. All `student_college_enrollments_*` dimensions and
measures should be stripped by `queryRewrite` (name starts with `student`,
triggering `isStudentMember`):

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-without-cube-access-student-data>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["student_college_enrollments_summary.count_college_enrollments"],
      "limit": 1
    }
  }' \
  | jq '.sql' | grep -c "1 = 0"
```

Expected: `1` — the default-deny filter is injected.

**Check 6 — Cube MCP `meta` lists new views:**

Use the `cube` MCP `meta` tool. The response should include
`student_college_enrollments_detail` and `student_college_enrollments_summary`
in the list of available views (visible to users with the appropriate access
groups).
