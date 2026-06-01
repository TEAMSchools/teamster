# Cube Family Communications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Prerequisite:**
`docs/superpowers/plans/2026-06-01-cube-model-yaml-implementation.md` (Plan 0)
must be fully merged before this plan runs. Plan 0 renames all cubes to drop
`dim_`/`fct_` prefixes and installs the `isStudentMember`/`isStaffMember`
naming-convention helpers in `cube.js`. This plan depends on those renamed cube
names (`student_enrollments`, `dates`, `staff`, etc.) and on the
`withSyntheticGroups` detail/summary access pattern.

**Goal:** Implement the family communications domain in the Cube semantic layer
— one cube file and two view files — mapping to
`kipptaf_marts.fct_family_communications`.

**Architecture:** One cube (`student_family_communications`) backed by
`kipptaf_marts.fct_family_communications`, two views
(`student_family_communications_detail` and
`student_family_communications_summary`). The cube name starts with `student_`
so `queryRewrite`'s `isStudentMember` helper automatically gates it on
`cube-access-student-data` — no static list update required. The fact also has a
`communicator_staff_key` FK to `dim_staff`; the staff join is declared on the
cube and exposed in the detail view. No direct `location_key` on the fact —
location is reached via `student_enrollments.locations`.

**Source dbt model:** `kipptaf_marts.fct_family_communications`
(`src/dbt/kipptaf/models/marts/facts/properties/fct_family_communications.yml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

**Tech Stack:** Cube YAML (`src/cube/model/`), Python tests (`pytest`, `pyyaml`)

---

## Key findings from the dbt property file

| Question                           | Answer                                                                              |
| ---------------------------------- | ----------------------------------------------------------------------------------- |
| Primary key                        | `family_communication_key` (string, surrogate)                                      |
| `date_key` FK to `dim_dates`       | Yes — `date_key` (DATE), direct FK                                                  |
| `student_enrollment_key` FK        | Yes — FK to `dim_student_enrollments`                                               |
| `location_key` FK                  | No — location is reached via `student_enrollments.locations`                        |
| `communicator_staff_key` FK        | Yes — FK to `dim_staff`; nullable (DeansList user may not resolve to staff)         |
| PII columns (`contains_pii: true`) | None explicitly tagged, but `notes` is free-text staff input (sensitive)            |
| Student data?                      | Yes — `student_enrollment_key` is the grain anchor                                  |
| Cube naming decision               | `student_family_communications` — `student_` prefix triggers `isStudentMember` gate |

**PII note on `notes`:** The `notes` column is free-text entered by staff
describing a family communication event. The dbt property file does not set
`contains_pii: true`, but FERPA's "linked or linkable" standard covers free-text
notes on student records. Tag `meta: {pii: true}` on the `notes` dimension and
exclude it from the detail view's `detail-access` block, unlocked only by
`cube-access-student-pii`.

**Staff join note:** `communicator_staff_key` is nullable — the DeansList user
who logged the communication may not resolve to a staff record. Declare the join
`relationship: many_to_one`; LEFT JOIN semantics mean rows with no matching
staff record still appear. No direct staff PII columns (name, email) are exposed
in the initial implementation — `communicator_staff_key` is a surrogate useful
for COUNT DISTINCT or joining to staff dims in advanced queries. If staff
display names are needed, expose `staff_full_name` in the detail view under
`cube-access-staff-pii` (add that excludes entry separately when implemented).

---

## Task 1: Add cube schema test coverage for the new domain

Extends the existing `tests/cube/test_cube_schema.py` from Plan 0 to also check
that view access policies reference valid groups.

**Files:**

- Modify: `tests/cube/test_cube_schema.py`

- [ ] **Step 1: Read the current test file**

```bash
uv run python -c "from pathlib import Path; print(Path('tests/cube/test_cube_schema.py').read_text())"
```

- [ ] **Step 2: Confirm the existing `test_cube_name_no_dim_or_fct_prefix`
      passes**

```bash
uv run pytest tests/cube/test_cube_schema.py::test_cube_name_no_dim_or_fct_prefix -v
```

Expected: all PASS (Plan 0 must be merged first).

- [ ] **Step 3: Add a view access-policy group allowlist test**

Append to `tests/cube/test_cube_schema.py`:

```python
VALID_ACCESS_GROUPS = {
    "detail-access",
    "summary-access",
    "cube-access-student-pii",
    "cube-access-staff-pii",
    "cube-access-staff-compensation",
    "cube-access-staff-benefits",
    "cube-access-staff-observations",
}


@pytest.mark.parametrize(
    "yaml_file",
    list((CUBE_MODEL_DIR / "views").rglob("*.yml")),
    ids=lambda p: str(p.relative_to(CUBE_MODEL_DIR)),
)
def test_view_access_policy_groups(yaml_file: Path) -> None:
    """View access_policy groups must be in the known allowlist.

    Catches typos in group names that would silently lock everyone out of a view.
    """
    data = yaml.safe_load(yaml_file.read_text())
    for view in data.get("views", []):
        for policy in view.get("access_policy", []):
            group = policy["group"]
            assert group in VALID_ACCESS_GROUPS, (
                f"{yaml_file.name}: view '{view['name']}' has unknown access group '{group}'"
            )
```

- [ ] **Step 4: Run the new test against existing view files to confirm it
      passes**

```bash
uv run pytest tests/cube/test_cube_schema.py::test_view_access_policy_groups -v
```

Expected: all existing view files PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/cube/test_cube_schema.py
git commit -m "test(cube): add view access-policy group allowlist test"
```

---

## Task 2: Create the cube file

Creates `src/cube/model/cubes/family_communications/family_communications.yml`.
Pattern 2 (fact-based domain cube): `sql_table`, joins to `dates`,
`student_enrollments`, and `staff`.

**Files:**

- Create directory: `src/cube/model/cubes/family_communications/`
- Create:
  `src/cube/model/cubes/family_communications/student_family_communications.yml`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p src/cube/model/cubes/family_communications
```

- [ ] **Step 2: Write the cube file**

Write the following as the complete content of
`src/cube/model/cubes/family_communications/student_family_communications.yml`:

```yaml
cubes:
  - name: student_family_communications
    public: false
    sql_table: kipptaf_marts.fct_family_communications

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

      # communicator_staff_key is nullable — DeansList user may not resolve to
      # a staff record. LEFT JOIN: rows with no match return NULL staff dims.
      - name: staff
        sql: "{staff.staff_key} = {CUBE}.communicator_staff_key"
        relationship: many_to_one

    dimensions:
      - name: family_communication_key
        sql: family_communication_key
        type: string
        primary_key: true

      - name: communication_date
        sql: CAST(date_key AS TIMESTAMP)
        type: time
        public: true

      - name: method
        sql: method
        type: string
        public: true

      - name: topic
        sql: topic
        type: string
        public: true

      - name: reason
        sql: reason
        type: string
        public: true

      - name: outcome
        sql: outcome
        type: string
        public: true

      - name: notes
        sql: notes
        type: string
        public: true
        meta:
          pii: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: is_attendance_call
        sql: is_attendance_call
        type: boolean
        public: true

      - name: is_truancy_call
        sql: is_truancy_call
        type: boolean
        public: true

      - name: communicator_staff_key
        sql: communicator_staff_key
        type: string
        public: true

    measures:
      - name: count_communications
        description: Total number of family communication events logged.
        sql: family_communication_key
        type: count_distinct
        public: true

      - name: count_students_contacted
        description:
          Distinct students (by enrollment) who received at least one
          communication.
        sql: student_enrollment_key
        type: count_distinct
        public: true

      - name: count_attendance_calls
        description: >-
          Family communications with is_attendance_call = true (reason starts
          with 'Att:'). Counts routine attendance outreach contacts.
        sql: family_communication_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_attendance_call = true"

      - name: count_truancy_calls
        description: >-
          Family communications with is_truancy_call = true (reason starts with
          'Chronic Absence:'). Counts chronic-absence / truancy intervention
          contacts.
        sql: family_communication_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_truancy_call = true"
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/cubes/family_communications/student_family_communications.yml').read_text()
)
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube['public'])
print('joins:', [j['name'] for j in cube['joins']])
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
print('pii dimensions:', [d['name'] for d in cube['dimensions'] if d.get('meta', {}).get('pii')])
"
```

Expected output:

```text
cube name: student_family_communications
public: False
joins: ['dates', 'student_enrollments', 'staff']
dimensions: ['family_communication_key', 'communication_date', 'method', 'topic', 'reason', 'outcome', 'notes', 'academic_year', 'is_attendance_call', 'is_truancy_call', 'communicator_staff_key']
measures: ['count_communications', 'count_students_contacted', 'count_attendance_calls', 'count_truancy_calls']
pii dimensions: ['notes']
```

- [ ] **Step 4: Run the cube schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py::test_cube_name_no_dim_or_fct_prefix -v
```

Expected: all PASS (new cube uses `student_family_communications`, no
`dim_`/`fct_` prefix).

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/family_communications/student_family_communications.yml
git commit -m "feat(cube): add student_family_communications cube (fct_family_communications)"
```

---

## Task 3: Create the detail view

Creates
`src/cube/model/views/family_communications/student_family_communications_detail.yml`.
Pattern: `group: detail-access` base block excludes `notes` (free-text PII);
`cube-access-student-pii` restores full access.

Location is reached via
`student_family_communications.student_enrollments.locations` — not directly on
the fact, so no diamond-path risk. Staff attributes are exposed minimally: only
`communicator_staff_key` as a grouping dimension (no staff name PII in the
initial implementation).

**Files:**

- Create directory: `src/cube/model/views/family_communications/`
- Create:
  `src/cube/model/views/family_communications/student_family_communications_detail.yml`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p src/cube/model/views/family_communications
```

- [ ] **Step 2: Write the detail view file**

Write the following as the complete content of
`src/cube/model/views/family_communications/student_family_communications_detail.yml`:

```yaml
views:
  - name: student_family_communications_detail
    description: >-
      Row-level family communication events from DeansList. One row per
      communication log entry between staff and a student's family. Scoped to
      enrolled-student recipients only.

      Communication type flags are mutually exclusive: is_attendance_call covers
      routine attendance outreach (reason starts with 'Att:'); is_truancy_call
      covers chronic-absence / truancy intervention workflow (reason starts with
      'Chronic Absence:'). For total attendance-related contacts use
      count_attendance_calls + count_truancy_calls. Neither flag is a subset of
      the other.

      The notes field contains free-text staff input and is gated behind
      cube-access-student-pii — it is excluded by default for detail-access
      users.

      communicator_staff_key links to the staff member who logged the
      communication; it is nullable when the DeansList user cannot be matched to
      a staff record.

    cubes:
      - join_path: student_family_communications
        includes:
          - count_communications
          - count_students_contacted
          - count_attendance_calls
          - count_truancy_calls
          - communication_date
          - method
          - topic
          - reason
          - outcome
          - notes
          - academic_year
          - is_attendance_call
          - is_truancy_call
          - communicator_staff_key

      - join_path: student_family_communications.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: student_family_communications.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_family_communications.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_family_communications.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year

      - join_path: student_family_communications.student_enrollments.students
        prefix: true
        includes:
          - student_key
          - full_name
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race

    meta:
      folders:
        - name: Communication
          members:
            - communication_date
            - method
            - topic
            - reason
            - outcome
            - notes
            - academic_year
            - is_attendance_call
            - is_truancy_call
            - communicator_staff_key
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
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
            - students_student_key
            - students_full_name
            - students_lea_student_identifier
            - students_state_student_identifier
            - students_gender_identity
            - students_race
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            # notes is free-text family communication content — FERPA-sensitive
            - notes
            # student direct identifiers
            - students_full_name
            - students_lea_student_identifier
            - students_state_student_identifier
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/views/family_communications/student_family_communications_detail.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
print('excluded members:', view['access_policy'][0]['member_level']['excludes'])
"
```

Expected output:

```text
view name: student_family_communications_detail
join paths: ['student_family_communications', 'student_family_communications.dates', 'student_family_communications.student_enrollments.locations', 'student_family_communications.student_enrollments.locations.regions', 'student_family_communications.student_enrollments', 'student_family_communications.student_enrollments.students']
access groups: ['detail-access', 'cube-access-student-pii']
excluded members: ['notes', 'students_full_name', 'students_lea_student_identifier', 'students_state_student_identifier']
```

- [ ] **Step 4: Run the view access-policy group test**

```bash
uv run pytest tests/cube/test_cube_schema.py::test_view_access_policy_groups -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/family_communications/student_family_communications_detail.yml
git commit -m "feat(cube): add student_family_communications_detail view"
```

---

## Task 4: Create the summary view

Creates
`src/cube/model/views/family_communications/student_family_communications_summary.yml`.
Summary view: no individual student identifiers, no `notes`, single
`summary-access` block. `date_day` is included for time-series trend analysis.

**Files:**

- Create:
  `src/cube/model/views/family_communications/student_family_communications_summary.yml`

- [ ] **Step 1: Write the summary view file**

Write the following as the complete content of
`src/cube/model/views/family_communications/student_family_communications_summary.yml`:

```yaml
views:
  - name: student_family_communications_summary
    description: >-
      Aggregated family communication counts by location, date, and
      communication type. No direct student identifiers — use for breakdowns,
      trend analysis, and volume reporting.

      Communication type flags are mutually exclusive: is_attendance_call covers
      routine attendance outreach (reason starts with 'Att:'); is_truancy_call
      covers chronic-absence / truancy intervention workflow (reason starts with
      'Chronic Absence:'). Neither is a subset of the other.

      For time-series analysis, use dates_date_day with a date range filter. For
      academic-year comparisons, group by dates_academic_year or academic_year
      (the degenerate dim on the fact row).

    cubes:
      - join_path: student_family_communications
        includes:
          - count_communications
          - count_students_contacted
          - count_attendance_calls
          - count_truancy_calls
          - method
          - topic
          - reason
          - outcome
          - academic_year
          - is_attendance_call
          - is_truancy_call

      - join_path: student_family_communications.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - academic_year

      - join_path: student_family_communications.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_family_communications.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_family_communications.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year

      - join_path: student_family_communications.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race

    meta:
      folders:
        - name: Communication
          members:
            - method
            - topic
            - reason
            - outcome
            - academic_year
            - is_attendance_call
            - is_truancy_call
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_academic_year
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
            - students_gender_identity
            - students_race
        - name: Enrollment
          members:
            - student_enrollments_grade_level
            - student_enrollments_graduation_year

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity) are aggregate
      # breakdowns only. notes is excluded entirely from this view.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(
    Path('src/cube/model/views/family_communications/student_family_communications_summary.yml').read_text()
)
view = data['views'][0]
print('view name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
view name: student_family_communications_summary
join paths: ['student_family_communications', 'student_family_communications.dates', 'student_family_communications.student_enrollments.locations', 'student_family_communications.student_enrollments.locations.regions', 'student_family_communications.student_enrollments', 'student_family_communications.student_enrollments.students']
access groups: ['summary-access']
```

- [ ] **Step 3: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/family_communications/student_family_communications_summary.yml
git commit -m "feat(cube): add student_family_communications_summary view"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode. Add
the branch by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads:**

```bash
# Compile a query against the summary view — 200 + SQL string confirms schema load
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["student_family_communications_summary.count_communications"],
      "dimensions": ["student_family_communications_summary.locations_location_name"],
      "limit": 1
    }
  }' | jq '.sql'
```

Expected: SQL string containing `fct_family_communications` as the FROM table.

**Check 2 — `student_` prefix triggers `isStudentMember` gate:**

Compile a query with a user who has no `cube-access-student-data` group. The
`queryRewrite` helper `isStudentMember` matches any member starting with
`student`, so `student_family_communications_summary.count_communications`
should be stripped, producing a query with `WHERE (1 = 0)` or an empty measure
set:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-without-cube-access-student-data>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["student_family_communications_summary.count_communications"],
      "limit": 1
    }
  }' | jq '.sql' | grep -c "1 = 0"
```

Expected: `1` (default-deny for users without student data access).

**Check 3 — `notes` excluded at `detail-access` level:**

Compile a query requesting the `notes` dimension with a `detail-access`-only JWT
(no `cube-access-student-pii`). Expect a "You requested hidden member" error or
an empty dimensions list in the compiled SQL:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/load" \
  -H "Authorization: <JWT-detail-access-no-pii>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "dimensions": ["student_family_communications_detail.notes"],
      "limit": 1
    }
  }' | jq '.error'
```

Expected: non-null error referencing hidden member.

**Check 4 — `meta` tool lists both views:**

```bash
curl -s "<DEV_MODE_URL>/cubejs-api/v1/meta" \
  -H "Authorization: <JWT-with-student-access-and-detail-scope>" \
  | jq '[.cubes[] | select(.name | startswith("student_family_communications")) | .name]'
```

Expected:

```json
[
  "student_family_communications_detail",
  "student_family_communications_summary"
]
```
