# Cube Model YAML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

## Execution Order

This is **Plan 0** — all other domain implementation plans depend on it. Run in
this order:

```text
0. cube-model-yaml-implementation                    ← this plan (run first)
   ├── cube-attendance-extension-implementation
   ├── cube-student-enrollments-implementation
   ├── cube-student-section-enrollments-implementation  (staff join requires staff-core)
   ├── cube-assessments-implementation
   ├── cube-family-communications-implementation
   ├── cube-gradebook-implementation
   ├── cube-postsecondary-implementation
   ├── cube-surveys-implementation
   └── cube-staff-core-implementation
          ├── cube-staff-hr-implementation
          └── cube-staff-observations-implementation
```

Plans at the same indent level are independent and can run in parallel once
their parent completes. Plans 0 → staff-core → staff-hr/observations must run in
sequence.

---

**Goal:** Rename all existing cube and view files to follow the spec's naming
convention, apply the `cube.js` security helper changes, and update the
attendance views' access policies — making `queryRewrite` enforce access
controls automatically on all future cubes without static list maintenance.

**Architecture:** All changes are in `src/cube/`. Cube names drop `dim_`/`fct_`
prefixes; `isStudentMember`/`isStaffMember` helpers + `withSyntheticGroups`
replace the static allowlists. Attendance views are renamed to
`student_attendance_*` and access policies are updated to the `detail-access` /
`summary-access` synthetic-group pattern. No dbt or Dagster changes required.

**Tech Stack:** Cube YAML (`src/cube/model/`), JavaScript (`cube.js`), Python
tests (`pytest`, `pyyaml`)

**PII tagging (applies to all domain plans):** Before writing each cube's
dimensions, grep the source dbt model's property YAML for `contains_pii: true`
and add `meta: {pii: true}` to every matching Cube dimension. Only
`dim_students` has these flags in dbt. `dim_staff` does NOT — use the spec's
explicit list instead: name fields, `birth_date`, emails, phone, AD username,
`staff_unique_id`, compensation fields. See `src/cube/CLAUDE.md` for the full
staff PII list.

**Dimension descriptions (applies to all domain plans):** Metadata sync (#3764)
is not yet live. When writing each cube's dimensions, copy the `description:`
from the source dbt model's property YAML. If a column has no description in
dbt, omit the field rather than writing a placeholder. When sync ships it will
populate missing descriptions and overwrite anything written here — so exact
wording matters less than coverage. Measure descriptions have no dbt equivalent
and must always be hand-authored.

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Task 1: Schema validation test

Establishes the pass/fail criterion for all cube rename tasks. Will fail on the
current state (all cubes use `dim_`/`fct_` prefixes) and pass once every cube is
renamed.

**Files:**

- Create: `tests/cube/test_cube_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cube/test_cube_schema.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CUBE_MODEL_DIR = Path(__file__).resolve().parents[2] / "src" / "cube" / "model"


@pytest.mark.parametrize(
    "yaml_file",
    list((CUBE_MODEL_DIR / "cubes").rglob("*.yml")),
    ids=lambda p: str(p.relative_to(CUBE_MODEL_DIR)),
)
def test_cube_name_no_dim_or_fct_prefix(yaml_file: Path) -> None:
    """Cube names must not start with dim_ or fct_.

    The naming convention drives queryRewrite security — see
    docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md#cube-naming-convention.
    """
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

- [ ] **Step 2: Run it to confirm it fails**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: multiple FAILs — `dim_dates`, `dim_locations`,
`dim_student_enrollments`, etc.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/cube/test_cube_schema.py
git commit -m "test(cube): add schema validation — cube names must not use dim_/fct_ prefix"
```

---

## Task 2: `cube.js` security helpers

Replaces the static `STUDENT_CUBES`/`STAFF_CUBES` allowlists with
naming-convention-driven helpers and adds `withSyntheticGroups` to emit
`detail-access`/`summary-access` synthetic groups. See
`docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md#cubejs-changes` for
the full rationale — apply exactly as shown there.

**Files:**

- Modify: `src/cube/cube.js`

- [ ] **Step 1: Replace the static arrays with helpers**

> **⚠️ Updated (PR #4010):** `SNAPSHOT_CUBES` and `SNAPSHOT_MEASURE_STEMS`
> arrays now exist in `cube.js` immediately after `STAFF_CUBES`. When replacing
> the block below, stop at the end of `STAFF_CUBES` — do **not** remove
> `SNAPSHOT_CUBES` or `SNAPSHOT_MEASURE_STEMS`.

In `src/cube/cube.js`, replace this block (immediately after
`nextMidnightEastern`), stopping before `SNAPSHOT_CUBES`:

```javascript
// STUDENT_CUBES: cubes that require cube-access-student-data.
// Add cube name: here when adding a new student-data cube.
const STUDENT_CUBES = [
  "attendance",
  "dim_student_ell_status",
  "dim_student_iep_status",
  "dim_student_meal_eligibility_status",
];

const STAFF_CUBES = [
  "dim_staff",
  "fct_staff_attrition",
  "fct_staff_observations",
];
```

With:

```javascript
// Naming convention drives security — no lists to maintain.
// student cubes: name starts with "student" (students, student_attendance, etc.)
// staff cubes:   name starts with "staff"   (staff, staff_attrition, etc.)
// conformed dims: bare business name (dates, locations, regions, terms, school_calendars)
function isStudentMember(m) {
  return m.startsWith("student");
}
function isStaffMember(m) {
  return m.startsWith("staff");
}

// Emit synthetic access groups so view access_policy blocks can gate on
// detail vs summary independently of the specific school/region group.
// These are NOT cached — derived fresh from the cached real groups on each
// contextToGroups call so the cache stays clean for queryRewrite lookups.
//
// Tier is derived from the SAME effective scope group that queryRewrite uses
// (network > region > school). A lower-priority detail group cannot escalate
// access beyond what the effective scope grants.
function withSyntheticGroups(cubeGroups) {
  const result = [...cubeGroups];
  const effectiveScope =
    cubeGroups.find((g) => g.startsWith("cube-network-")) ??
    cubeGroups.find((g) =>
      /^cube-region-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    ) ??
    cubeGroups.find((g) =>
      /^cube-school-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    );
  if (effectiveScope?.endsWith("-detail")) result.push("detail-access");
  if (
    effectiveScope?.endsWith("-detail") ||
    effectiveScope?.endsWith("-summary")
  )
    result.push("summary-access");
  return result;
}
```

- [ ] **Step 2: Wrap all three `contextToGroups` return sites**

Find the three `return` statements that return groups and wrap each:

```javascript
// 1. CUBE_GROUP_MAP branch (local dev) — was: return groups;
return withSyntheticGroups(groups);

// 2. Cache hit branch — was: return cached.groups;
return withSyntheticGroups(cached.groups);

// 3. Admin API branch (after storing to cache) — was: return cubeGroups;
return withSyntheticGroups(cubeGroups);
```

- [ ] **Step 3: Update `queryRewrite` to use helpers**

Replace the STUDENT_CUBES filter in `queryRewrite`:

```javascript
// was:
dimensions: (query.dimensions ?? []).filter(
  (d) => !STUDENT_CUBES.some((c) => d.startsWith(c)),
),
measures: (query.measures ?? []).filter(
  (m) => !STUDENT_CUBES.some((c) => m.startsWith(c)),
),

// becomes:
dimensions: (query.dimensions ?? []).filter((d) => !isStudentMember(d)),
measures: (query.measures ?? []).filter((m) => !isStudentMember(m)),
```

Replace the STAFF_CUBES check:

```javascript
// was:
].some((m) => STAFF_CUBES.some((c) => m.startsWith(c)));

// becomes:
].some((m) => isStaffMember(m));
```

- [ ] **Step 4: Update location filter member references**

Three `member:` strings in `queryRewrite` still reference `dim_locations`.
Update all three:

```javascript
// region filter
member: "locations.region_key",

// school filter
member: "locations.abbreviation",

// default-deny filter (in the else branch)
member: "locations.abbreviation",
```

- [ ] **Step 5: Verify the file parses**

```bash
node -e "require('./src/cube/cube.js')" 2>&1 | head -5
```

Expected: no output (clean parse, `module.exports` is an object literal, no
top-level side effects).

- [ ] **Step 6: Commit**

```bash
git add src/cube/cube.js
git commit -m "feat(cube): replace STUDENT_CUBES/STAFF_CUBES with prefix helpers; add withSyntheticGroups"
```

---

## Task 3: Rename conformed cubes

Remove `dim_` prefix from all five conformed cube names. These cubes are join
targets — their names appear in join declarations across domain cubes, so rename
here first before touching domain cubes. The `locations` cube also declares a
join to `regions`; update that reference too.

**Files:**

- Modify: `src/cube/model/cubes/conformed/dates.yml`
- Modify: `src/cube/model/cubes/conformed/locations.yml`
- Modify: `src/cube/model/cubes/conformed/regions.yml`
- Modify: `src/cube/model/cubes/conformed/terms.yml`
- Modify: `src/cube/model/cubes/conformed/school_calendars.yml`

- [ ] **Step 1: Rename dates cube**

In `dates.yml`, change:

```yaml
- name: dim_dates
```

To:

```yaml
- name: dates
```

- [ ] **Step 2: Rename regions cube**

In `regions.yml`, change:

```yaml
- name: dim_regions
```

To:

```yaml
- name: regions
```

- [ ] **Step 3: Rename locations cube (+ update its join reference)**

In `locations.yml`, change the cube name:

```yaml
- name: dim_locations
```

To:

```yaml
- name: locations
```

And update its join to `regions` (was `dim_regions`):

```yaml
joins:
  - name: regions
    sql: "{regions.region_key} = {CUBE}.region_key"
    relationship: many_to_one
```

- [ ] **Step 4: Rename terms cube**

In `terms.yml`, change:

```yaml
- name: dim_terms
```

To:

```yaml
- name: terms
```

- [ ] **Step 5: Rename school_calendars cube**

In `school_calendars.yml`, change:

```yaml
- name: dim_school_calendars
```

To:

```yaml
- name: school_calendars
```

- [ ] **Step 5: Run schema test — should show fewer failures**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: conformed cube tests now PASS; student and attendance cube tests still
FAIL.

- [ ] **Step 6: Commit**

```bash
git add src/cube/model/cubes/conformed/
git commit -m "refactor(cube): rename conformed cubes — drop dim_ prefix (dates, locations, regions, terms, school_calendars)"
```

---

## Task 4: Rename student-domain cubes

Remove `dim_` prefix from the student base dim (`students`), the enrollment dim
(`student_enrollments`), and the three SCD2 status dims. The enrollment cube
also declares joins to `dim_students` and `dim_locations` — update those join
names to the new cube names.

**Files:**

- Modify: `src/cube/model/cubes/students/students.yml`
- Modify: `src/cube/model/cubes/students/student_enrollments.yml`
- Modify: `src/cube/model/cubes/students/student_ell_status.yml`
- Modify: `src/cube/model/cubes/students/student_iep_status.yml`
- Modify: `src/cube/model/cubes/students/student_meal_eligibility_status.yml`

- [ ] **Step 1: Rename students cube**

In `students.yml`, change:

```yaml
- name: dim_students
```

To:

```yaml
- name: students
```

- [ ] **Step 2: Rename student_enrollments cube (+ update join references)**

In `student_enrollments.yml`, change the cube name:

```yaml
- name: dim_student_enrollments
```

To:

```yaml
- name: student_enrollments
```

Update its `joins:` block to use new cube names:

```yaml
joins:
  - name: students
    sql: "{students.student_key} = {CUBE}.student_key"
    relationship: many_to_one

  - name: locations
    sql: "{locations.location_key} = {CUBE}.location_key"
    relationship: many_to_one
```

- [ ] **Step 3: Rename student_ell_status cube**

In `student_ell_status.yml`, change:

```yaml
- name: dim_student_ell_status
```

To:

```yaml
- name: student_ell_status
```

- [ ] **Step 4: Rename student_iep_status cube**

In `student_iep_status.yml`, change:

```yaml
- name: dim_student_iep_status
```

To:

```yaml
- name: student_iep_status
```

- [ ] **Step 5: Rename student_meal_eligibility_status cube**

In `student_meal_eligibility_status.yml`, change:

```yaml
- name: dim_student_meal_eligibility_status
```

To:

```yaml
- name: student_meal_eligibility_status
```

- [ ] **Step 5: Run schema test — only attendance cube should still fail**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: conformed + student cube tests PASS; `attendance/attendance.yml` still
FAILS.

- [ ] **Step 6: Commit**

```bash
git add src/cube/model/cubes/students/
git commit -m "refactor(cube): rename student-domain cubes — drop dim_ prefix, update enrollment joins"
```

---

## Task 5: Rename and update the attendance fact cube

Rename the file from `attendance.yml` to `student_attendance.yml` and update the
cube name plus all seven join references to use the new cube names from Tasks 3
and 4. Also update two measure filter references that cross-reference
`dim_students` and `dim_dates` by the old names.

**Files:**

- Rename: `src/cube/model/cubes/attendance/attendance.yml` →
  `src/cube/model/cubes/attendance/student_attendance.yml`

- [ ] **Step 1: Rename the file**

```bash
git mv src/cube/model/cubes/attendance/attendance.yml \
       src/cube/model/cubes/attendance/student_attendance.yml
```

- [ ] **Step 2: Update the cube name**

In `student_attendance.yml`, change:

```yaml
- name: attendance
```

To:

```yaml
- name: student_attendance
```

- [ ] **Step 3: Update all join names and SQL references**

> **⚠️ Updated (PR #4010):** The attendance cube now has all 7 joins already
> declared. Do NOT replace the entire block — only rename the `dim_*` prefixes.

For each join in `student_attendance.yml`, rename:

| Old join `name:`                      | New join `name:`                  |
| ------------------------------------- | --------------------------------- |
| `dim_dates`                           | `dates`                           |
| `dim_student_enrollments`             | `student_enrollments`             |
| `dim_school_calendars`                | `school_calendars`                |
| `dim_terms`                           | `terms`                           |
| `dim_student_ell_status`              | `student_ell_status`              |
| `dim_student_iep_status`              | `student_iep_status`              |
| `dim_student_meal_eligibility_status` | `student_meal_eligibility_status` |

Update every `{dim_*.*}` reference in join `sql:` fields to match the new names.
For example:

```yaml
# was:
- name: dim_dates
  sql: "{dim_dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"

# becomes:
- name: dates
  sql: "{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"
```

The `dim_school_calendars` join also references
`{dim_student_enrollments.location_key}` — update that reference too:

```yaml
# was:
  sql: >
    {dim_school_calendars.date_key} = {CUBE}.date_key AND
    {dim_school_calendars.location_key} = {dim_student_enrollments.location_key}

# becomes:
  sql: >
    {school_calendars.date_key} = {CUBE}.date_key AND
    {school_calendars.location_key} = {student_enrollments.location_key}
```

- [ ] **Step 4: Update cross-cube measure filter references**

Two measures reference `{dim_students.*}` and `{dim_dates.*}` in their
`filters:` SQL. Update both. Search for `dim_students` and `dim_dates` in the
file and replace:

```yaml
# was: {dim_students.enrollment_status}
{students.enrollment_status}

# was: {dim_dates.is_current_academic_year}
{dates.is_current_academic_year}
```

These appear in the `_count_ca_eligible_students`, `count_chronically_absent`,
`_count_tier_1_2`, and `_count_tier_3` measures.

- [ ] **Step 5: Update `SNAPSHOT_CUBES` in `cube.js`**

`SNAPSHOT_CUBES` still contains `"attendance"` (the old cube name). Update it to
match the renamed cube:

```javascript
// was:
const SNAPSHOT_CUBES = ["attendance"];

// becomes:
const SNAPSHOT_CUBES = ["student_attendance"];
```

- [ ] **Step 5: Run schema test — all cube tests should now pass**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/cube/model/cubes/attendance/ src/cube/cube.js
git commit -m "refactor(cube): rename attendance cube to student_attendance; update all join references"
```

---

## Task 6: Rewrite the attendance detail view

Rename the view file, update all join paths to use the new cube names, update
`meta.folders` member names (the prefix changes because join names changed), and
fix the access policy to use the `detail-access` / `cube-access-student-pii`
pattern from the spec.

**Key rule:** `prefix: true` on a join path prepends the **join name** (last
segment) to every field. So `join_path: student_attendance.dates` with
`prefix: true` → fields become `dates_*`. Access policy `excludes:` must use the
post-prefix names.

**Files:**

- Rename: `src/cube/model/views/attendance/attendance_detail.yml` →
  `src/cube/model/views/attendance/student_attendance_detail.yml`

- [ ] **Step 1: Rename the file**

```bash
git mv src/cube/model/views/attendance/attendance_detail.yml \
       src/cube/model/views/attendance/student_attendance_detail.yml
```

- [ ] **Step 2: Replace the entire file content**

Write the following as the complete content of
`src/cube/model/views/attendance/student_attendance_detail.yml`:

```yaml
views:
  - name: student_attendance_detail
    description: >-
      Row-level student attendance. One row per student × school day with
      attendance recorded. Use for drill-down, individual investigations, or
      breakdowns that need raw codes; for ADA / truancy roll-ups, use
      student_attendance_summary instead. ADA is always SUM(attendance_value) /
      SUM(membership_value); never average a per-row ratio. attendance_value
      (0.0–1.0) is the fractional attendance contribution; membership_value
      (0.0–1.0) is the school's claim on the student that day (split across
      schools if dual-enrolled); present_weight equals attendance_value but
      tardies count 0.67. attendance_category is the coarse rollup (Present,
      Absent, Tardy, In-School Suspension, Out-of-School Suspension);
      attendance_code is the raw SIS code for specific drill-down. is_in_session
      and is_membership_day come from school_calendars and are joined on
      (date_key, student_enrollments.location_key). Contains direct student
      identifiers — see access_policy for PII gating.

      Chronic absence and truancy query patterns. For unanchored CA or truancy
      measures (count_chronically_absent, pct_tier_1_2, is_truant, etc.),
      queryRewrite auto-injects the correct snapshot anchor based on query shape
      — no manual filter required in most BI tools. For SQL API or Superset,
      apply the anchor explicitly.

      Named period-end measures (_year_end, _month_end, _week_end) have the
      anchor baked into their SQL filters and bypass auto-injection. Use these
      for period-specific trend analysis:

      (1) Year-end / year-over-year: use pct_chronically_absent_year_end grouped
      by academic_year. Returns the CA rate at the final snapshot of each year.
      "CA rate in 2023 vs 2024 vs 2025."

      (2) Month-over-month trend: use pct_chronically_absent_month_end with
      timeDimensions granularity "month". Returns CA at each month-end snapshot.
      Requires granularity: "month" — queryRewrite enforces this.

      (3) Point-in-time (same date across years): filter to a single date_day
      using filters (not timeDimensions). Returns CA accumulated from year start
      through that date. "CA as of November 1 each year." queryRewrite
      recognises a single-date filter and does not inject is_latest_record.

      Omitting all anchors on unanchored measures will overcount — but
      queryRewrite prevents this automatically for REST API consumers.

      For truancy, the same three patterns apply using the _year_end /
      _month_end / _week_end truancy measures. Truancy criteria are regional:
      Miami uses 15+ absences in a 90-day rolling window; NJ regions use
      projected 50+ absences for the year.

    cubes:
      - join_path: student_attendance
        includes:
          - count_students
          - avg_daily_attendance
          - pct_tardy
          - pct_ontime
          - count_truants
          - pct_truant
          - count_truants_year_end
          - pct_truant_year_end
          - count_truants_month_end
          - pct_truant_month_end
          - count_truants_week_end
          - pct_truant_week_end
          - count_absent_days
          - count_chronically_absent
          - pct_chronically_absent
          - pct_tier_1_2
          - pct_tier_3
          - count_chronically_absent_year_end
          - pct_chronically_absent_year_end
          - pct_tier_1_2_year_end
          - pct_tier_3_year_end
          - count_chronically_absent_month_end
          - pct_chronically_absent_month_end
          - pct_tier_1_2_month_end
          - pct_tier_3_month_end
          - count_chronically_absent_week_end
          - pct_chronically_absent_week_end
          - pct_tier_1_2_week_end
          - pct_tier_3_week_end
          - attendance_date
          - attendance_code
          - attendance_category
          - ada_tier
          - attendance_value
          - membership_value
          - present_weight
          - is_absent
          - is_tardy
          - is_ontime
          - is_oss
          - is_iss
          - is_suspended
          - is_truant
          - is_chronically_absent
          - is_latest_record
          - is_month_end_record
          - is_week_end_record

      - join_path: student_attendance.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - quarter_number
          - school_week_start_date
          - day_of_week_name
          - is_weekday

      - join_path: student_attendance.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_attendance.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_attendance.student_enrollments
        prefix: true
        includes:
          - student_enrollment_key
          - grade_level
          - graduation_year
          - entry_date
          - exit_date
          - is_retained_year

      - join_path: student_attendance.student_enrollments.students
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

      - join_path: student_attendance.student_ell_status
        prefix: true
        includes:
          - is_ell

      - join_path: student_attendance.student_iep_status
        prefix: true
        includes:
          - is_iep
          - iep_classification
          - special_education_code
          - special_education_name
          - special_education_placement

      - join_path: student_attendance.student_meal_eligibility_status
        prefix: true
        includes:
          - is_meal_eligible
          - meal_eligibility

      - join_path: student_attendance.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: student_attendance.school_calendars
        prefix: true
        includes:
          - is_in_session
          - is_membership_day

    meta:
      folders:
        - name: Attendance
          members:
            - attendance_code
            - attendance_category
            - ada_tier
            - attendance_value
            - membership_value
            - present_weight
            - is_absent
            - is_tardy
            - is_ontime
            - is_oss
            - is_iss
            - is_suspended
            - is_truant
            - is_chronically_absent
        - name: Date
          members:
            - attendance_date
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_quarter_number
            - dates_school_week_start_date
            - dates_day_of_week_name
            - dates_is_weekday
        - name: Term
          members:
            - terms_academic_year
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
            - students_student_key
            - students_full_name
            - students_birth_date
            - students_lea_student_identifier
            - students_state_student_identifier
            - students_gender_identity
            - students_race
            - students_enrollment_status
            - students_is_gifted
            - student_ell_status_is_ell
            - student_iep_status_is_iep
            - student_iep_status_iep_classification
            - student_iep_status_special_education_code
            - student_iep_status_special_education_name
            - student_iep_status_special_education_placement
            - student_meal_eligibility_status_is_meal_eligible
            - student_meal_eligibility_status_meal_eligibility
        - name: Enrollment
          members:
            - student_enrollments_student_enrollment_key
            - student_enrollments_grade_level
            - student_enrollments_graduation_year
            - student_enrollments_entry_date
            - student_enrollments_exit_date
            - student_enrollments_is_retained_year
        - name: Calendar
          members:
            - school_calendars_is_in_session
            - school_calendars_is_membership_day
        - name: Filter
          members:
            - is_latest_record
            - is_month_end_record
            - is_week_end_record

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

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/attendance/student_attendance_detail.yml').read_text())
print('view name:', data['views'][0]['name'])
print('join paths:', [c['join_path'] for c in data['views'][0]['cubes']])
"
```

Expected output:

```text
view name: student_attendance_detail
join paths: ['student_attendance', 'student_attendance.dates', 'student_attendance.student_enrollments.locations', ...]
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/attendance/
git commit -m "refactor(cube): rename attendance_detail to student_attendance_detail; fix join paths and access policy"
```

---

## Task 7: Rewrite the attendance summary view

Same rename pattern as Task 6. Summary view has no individual identifiers so the
access policy is a single `summary-access` block — no `excludes` needed.

**Files:**

- Rename: `src/cube/model/views/attendance/attendance_summary.yml` →
  `src/cube/model/views/attendance/student_attendance_summary.yml`

- [ ] **Step 1: Rename the file**

```bash
git mv src/cube/model/views/attendance/attendance_summary.yml \
       src/cube/model/views/attendance/student_attendance_summary.yml
```

- [ ] **Step 2: Replace the entire file content**

Write the following as the complete content of
`src/cube/model/views/attendance/student_attendance_summary.yml`:

```yaml
views:
  - name: student_attendance_summary
    description: >-
      Aggregated student attendance for ADA, tardy rate, and truancy breakdowns.
      One row per filter slice — never per student-day. ADA is always
      SUM(attendance_value) / SUM(membership_value); never average a per-row
      ratio. attendance_category is the coarse rollup (Present, Absent, Tardy,
      In-School Suspension, Out-of-School Suspension); use it for GROUP BY
      breakdowns instead of attempting to sum the boolean is_* flags. No direct
      student identifiers — demographic dimensions are aggregate breakdowns
      only.

      Chronic absence and truancy query patterns. For unanchored CA or truancy
      measures, queryRewrite auto-injects the correct snapshot anchor — no
      manual filter required in most BI tools. Named period-end measures
      (_year_end, _month_end, _week_end) have anchors baked in and bypass
      injection.

      (1) Year-end / year-over-year: use pct_chronically_absent_year_end grouped
      by academic_year. "CA rate in 2023 vs 2024 vs 2025."

      (2) Month-over-month trend: use pct_chronically_absent_month_end with
      timeDimensions granularity "month". Requires granularity: "month" —
      queryRewrite enforces this and throws if missing.

      (3) Point-in-time (same date across years): filter to a single date_day
      using filters (not timeDimensions). queryRewrite recognises a single-date
      filter and does not inject is_latest_record.

      For truancy, the same three patterns apply using the _year_end /
      _month_end / _week_end truancy measures. Truancy criteria are regional:
      Miami uses 15+ absences in a 90-day rolling window; NJ regions use
      projected 50+ absences for the year.

    cubes:
      - join_path: student_attendance
        includes:
          - count_students
          - avg_daily_attendance
          - pct_tardy
          - pct_ontime
          - count_truants
          - pct_truant
          - count_truants_year_end
          - pct_truant_year_end
          - count_truants_month_end
          - pct_truant_month_end
          - count_truants_week_end
          - pct_truant_week_end
          - count_absent_days
          - count_chronically_absent
          - pct_chronically_absent
          - pct_tier_1_2
          - pct_tier_3
          - count_chronically_absent_year_end
          - pct_chronically_absent_year_end
          - pct_tier_1_2_year_end
          - pct_tier_3_year_end
          - count_chronically_absent_month_end
          - pct_chronically_absent_month_end
          - pct_tier_1_2_month_end
          - pct_tier_3_month_end
          - count_chronically_absent_week_end
          - pct_chronically_absent_week_end
          - pct_tier_1_2_week_end
          - pct_tier_3_week_end
          - attendance_category
          - ada_tier
          - is_truant
          - is_chronically_absent
          - is_latest_record
          - is_month_end_record
          - is_week_end_record

      - join_path: student_attendance.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - quarter_number
          - school_week_start_date

      - join_path: student_attendance.student_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_attendance.student_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_attendance.student_enrollments
        prefix: true
        includes:
          - grade_level
          - graduation_year
          - is_retained_year

      - join_path: student_attendance.student_enrollments.students
        prefix: true
        includes:
          - gender_identity
          - race
          - is_gifted

      - join_path: student_attendance.student_ell_status
        prefix: true
        includes:
          - is_ell

      - join_path: student_attendance.student_iep_status
        prefix: true
        includes:
          - is_iep
          - iep_classification
          - special_education_code
          - special_education_name
          - special_education_placement

      - join_path: student_attendance.student_meal_eligibility_status
        prefix: true
        includes:
          - is_meal_eligible
          - meal_eligibility

      - join_path: student_attendance.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

    meta:
      folders:
        - name: Attendance
          members:
            - attendance_category
            - ada_tier
            - is_truant
            - is_chronically_absent
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_quarter_number
            - dates_school_week_start_date
        - name: Term
          members:
            - terms_academic_year
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
            - students_gender_identity
            - students_race
            - students_is_gifted
            - student_ell_status_is_ell
            - student_iep_status_is_iep
            - student_iep_status_iep_classification
            - student_iep_status_special_education_code
            - student_iep_status_special_education_name
            - student_iep_status_special_education_placement
            - student_meal_eligibility_status_is_meal_eligible
            - student_meal_eligibility_status_meal_eligibility
        - name: Enrollment
          members:
            - student_enrollments_grade_level
            - student_enrollments_graduation_year
            - student_enrollments_is_retained_year
        - name: Filter
          members:
            - is_latest_record
            - is_month_end_record
            - is_week_end_record

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, etc.) are
      # aggregate breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/attendance/student_attendance_summary.yml').read_text())
print('view name:', data['views'][0]['name'])
print('access groups:', [p['group'] for p in data['views'][0]['access_policy']])
"
```

Expected output:

```text
view name: student_attendance_summary
access groups: ['summary-access']
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS including `test_cube_schema.py`.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/attendance/
git commit -m "refactor(cube): rename attendance_summary to student_attendance_summary; fix join paths and access policy"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate the changes in Cube Cloud Dev
Mode. Dev Mode (per-developer branch endpoint) is the only environment where
server `console.log` output is visible — staging has no log UI. Add the branch
by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads:**

```bash
# compile a query against the new view name; a 200 response confirms the schema loads
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_attendance_summary.count_students"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string containing `student_attendance` as the FROM table alias.

**Check 2 — Old view names are gone:**

The Cube MCP `meta` tool should no longer list `attendance_detail` or
`attendance_summary`; it should list `student_attendance_detail` and
`student_attendance_summary`.

**Check 3 — Security gate works (queryRewrite default-deny):**

Compile a query with a user who has no scope group — the SQL should contain
`WHERE (1 = 0)` and `rlsAccessDenied` in `sortedDimensions`:

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-with-no-scope-group>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["student_attendance_summary.count_students"],"limit":1}}' \
  | jq '.sql' | grep -c "1 = 0"
```

Expected: `1`.
