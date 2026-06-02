# Cube Staff Observations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Staff Observations domain in the Cube semantic layer —
cube files for `staff_observations`, `staff_observer` (role alias), and
`staff_reporting_relationships` + `staff_manager` (point-in-time manager
resolver), plus detail and summary views with Pattern 5 access policy (column
gate + row-level scoping).

**Prerequisite:** The Staff Core plan must run first. `staff.yml` must exist at
`src/cube/model/cubes/staff/staff.yml` before this plan begins —
`staff_observer` extends it and `staff_reporting_relationships` joins it. Do not
start this plan until that file is present.

**Architecture:** Five new files in `src/cube/`. The fact cube
(`staff_observations.yml`) maps `fct_staff_observations` with two FK paths to
`dim_staff` — the primary teacher FK joins `staff` directly; the secondary
observer FK joins `staff_observer` (a role alias cube that `extends: staff`).
Point-in-time manager is resolved via `staff_reporting_relationships` (a
subquery cube) and `staff_manager` (another `extends: staff` alias). No dbt or
Dagster changes required.

**Blocker note:** `pct_evaluated` and `pct_assigned_goals` require a count of
eligible teachers as the denominator. This requires an `is_teaching_role` flag
on `dim_staff_work_assignments` (blocked by issue #3839). These two measures are
NOT implemented in this plan. All other measures — `count_observations`,
`avg_score`, `count_by_overall_rating` — are implementable now and are included
below.

**Source table:** `kipptaf_marts.fct_staff_observations`

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

**Tech Stack:** Cube YAML (`src/cube/model/`), Python tests (`pytest`, `pyyaml`)

---

## Task 1: Schema validation test extension

Extends the existing `tests/cube/test_cube_schema.py` to cover staff observation
cube files. The test verifies that all new cube files parse as valid YAML and
use the correct naming convention (no `dim_`/`fct_` prefix).

**Files:**

- Verify existing: `tests/cube/test_cube_schema.py`

- [ ] **Step 1: Confirm the test file exists and covers the staff/ directory**

```bash
uv run pytest tests/cube/test_cube_schema.py -v --collect-only 2>&1 | head -20
```

Expected: test collection succeeds. The parametrized test uses `rglob("*.yml")`
on the full `cubes/` directory, so staff cube files will automatically be picked
up once created.

- [ ] **Step 2: Run the test baseline before writing any files**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all current tests PASS. Record the passing count — staff observation
tests will be added by creating the files in subsequent tasks.

---

## Task 2: `staff_observer.yml` — role alias cube

Creates the role alias cube that extends `staff` to provide a distinct join
target for the observer FK on `fct_staff_observations`. This file must exist
before `staff_observations.yml` declares a join to it.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_observer.yml`

- [ ] **Step 1: Create `src/cube/model/cubes/staff/` directory if it does not
      exist**

```bash
ls src/cube/model/cubes/staff/ 2>/dev/null || mkdir -p src/cube/model/cubes/staff/
```

- [ ] **Step 2: Write `staff_observer.yml`**

```yaml
cubes:
  - name: staff_observer
    extends: staff
    public: false
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_observer.yml').read_text())
cube = data['cubes'][0]
print('name:', cube['name'])
print('extends:', cube['extends'])
print('public:', cube['public'])
"
```

Expected output:

```text
name: staff_observer
extends: staff
public: False
```

- [ ] **Step 4: Run schema test — new file should PASS**

```bash
uv run pytest tests/cube/test_cube_schema.py -v -k "staff_observer"
```

Expected: PASS (no `dim_` or `fct_` prefix).

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/staff/staff_observer.yml
git commit -m "feat(cube): add staff_observer role alias cube (extends staff)"
```

---

## Task 3: `staff_reporting_relationships.yml` and `staff_manager.yml` — verify exist from staff-core plan

> **These files are created by the Staff Core plan (Tasks 4 and 5) — do NOT
> recreate them here.** The staff-core plan is a prerequisite; both files must
> already be on disk before this task runs.

**Files:**

- Verify exists: `src/cube/model/cubes/staff/staff_reporting_relationships.yml`
- Verify exists: `src/cube/model/cubes/staff/staff_manager.yml`

- [ ] **Step 1: Confirm both files exist with correct content**

```bash
uv run python -c "
import yaml
from pathlib import Path

for fname in ['staff_reporting_relationships.yml', 'staff_manager.yml']:
    data = yaml.safe_load(Path(f'src/cube/model/cubes/staff/{fname}').read_text())
    cube = data['cubes'][0]
    print(f'{fname}: name={cube[\"name\"]}', end='')
    if 'extends' in cube:
        print(f', extends={cube[\"extends\"]}', end='')
    if 'dimensions' in cube:
        print(f', dimensions={[d[\"name\"] for d in cube[\"dimensions\"]]}', end='')
    print()
"
```

Expected output (matches staff-core plan Tasks 4 & 5):

```text
staff_reporting_relationships.yml: name=staff_reporting_relationships, dimensions=['staff_reporting_relationship_key', 'staff_key', 'manager_staff_key', 'effective_start_date', 'effective_end_date']
staff_manager.yml: name=staff_manager, extends=staff
```

If either file is missing, the staff-core plan has not been run — stop and
complete it first.

---

## Task 4: `staff_observations.yml` — fact cube

The core fact cube. Maps `fct_staff_observations` with `sql_table:`. Declares
four joins:

1. `dates` — on `observed_date_key` (the observation date FK)
2. `staff` — on `teacher_staff_key` (the observed teacher; primary FK)
3. `staff_observer` — on `observer_staff_key` (the observer; secondary
   role-playing FK)
4. `locations` — direct FK (`location_key` is on the fact, no student
   enrollments intermediate)
5. `terms` — on `term_key`
6. `staff_reporting_relationships` — point-in-time manager resolver anchored on
   `teacher_staff_key` and `observed_date_key`
7. `staff_manager` — via `staff_reporting_relationships.manager_staff_key`

All dimensions from `fct_staff_observations` with `meta: {pii: true}` on the
seven observation content fields (`score`, `overall_rating`, `notes`,
`positive_feedback`, `growth_areas`) per Pattern 5. `observed_timestamp` is a
direct TIMESTAMP from the fact (no cast needed).

**Measures:** `count_observations`, `avg_score`, and four
`count_by_overall_rating_N` measures (one per rating 1–4). `pct_evaluated` and
`pct_assigned_goals` are NOT included — blocked by issue #3839
(`is_teaching_role` flag missing from `dim_staff_work_assignments`).

**Files:**

- Create: `src/cube/model/cubes/staff/staff_observations.yml`

- [ ] **Step 1: Write `staff_observations.yml`**

```yaml
cubes:
  - name: staff_observations
    public: false
    sql_table: kipptaf_marts.fct_staff_observations

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.observed_date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: locations
        sql: "{locations.location_key} = {CUBE}.location_key"
        relationship: many_to_one

      - name: terms
        sql: "{terms.term_key} = {CUBE}.term_key"
        relationship: many_to_one

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.teacher_staff_key"
        relationship: many_to_one

      - name: staff_observer
        sql: "{staff_observer.staff_key} = {CUBE}.observer_staff_key"
        relationship: many_to_one

      - name: staff_reporting_relationships
        relationship: many_to_one
        sql: >
          {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key
          AND CAST({CUBE}.observed_date_key AS TIMESTAMP)
              BETWEEN CAST({staff_reporting_relationships.effective_start_date}
          AS TIMESTAMP)
              AND     CAST({staff_reporting_relationships.effective_end_date}   AS
          TIMESTAMP)

      - name: staff_manager
        sql: >
          {staff_manager.staff_key} =
          {staff_reporting_relationships.manager_staff_key}
        relationship: many_to_one

    dimensions:
      - name: staff_observation_key
        sql: staff_observation_key
        type: string
        primary_key: true

      - name: teacher_staff_key
        sql: teacher_staff_key
        type: string
        public: true
        meta:
          pii: true

      - name: observer_staff_key
        sql: observer_staff_key
        type: string
        public: true
        meta:
          pii: true

      - name: location_key
        sql: location_key
        type: string
        public: true

      - name: term_key
        sql: term_key
        type: string
        public: true

      - name: observed_date_key
        sql: CAST(observed_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: observed_timestamp
        sql: observed_timestamp
        type: time
        public: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: score
        sql: score
        type: number
        public: true
        meta:
          pii: true

      - name: overall_rating
        sql: overall_rating
        type: number
        public: true
        meta:
          pii: true

      - name: notes
        sql: notes
        type: string
        public: true
        meta:
          pii: true

      - name: positive_feedback
        sql: positive_feedback
        type: string
        public: true
        meta:
          pii: true

      - name: growth_areas
        sql: growth_areas
        type: string
        public: true
        meta:
          pii: true

      - name: is_locked
        sql: is_locked
        type: boolean
        public: true

    measures:
      - name: count_observations
        description: Total number of observations.
        sql: staff_observation_key
        type: count_distinct
        public: true

      - name: _sum_score
        sql: score
        type: sum
        public: false

      - name: _count_scored
        sql: staff_observation_key
        type: count_distinct
        public: false
        filters:
          - sql: "{CUBE}.score IS NOT NULL"

      - name: avg_score
        description: Average observation score across all scored observations.
        sql: "{_sum_score} / NULLIF({_count_scored}, 0)"
        type: number
        public: true

      - name: count_overall_rating_1
        description: Count of observations with overall rating of 1.
        sql: staff_observation_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.overall_rating = 1"

      - name: count_overall_rating_2
        description: Count of observations with overall rating of 2.
        sql: staff_observation_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.overall_rating = 2"

      - name: count_overall_rating_3
        description: Count of observations with overall rating of 3.
        sql: staff_observation_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.overall_rating = 3"

      - name: count_overall_rating_4
        description: Count of observations with overall rating of 4.
        sql: staff_observation_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.overall_rating = 4"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_observations.yml').read_text())
cube = data['cubes'][0]
print('name:', cube['name'])
print('joins:', [j['name'] for j in cube['joins']])
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
pii_dims = [d['name'] for d in cube['dimensions'] if d.get('meta', {}).get('pii')]
print('pii dims:', pii_dims)
"
```

Expected output:

```text
name: staff_observations
joins: ['dates', 'locations', 'terms', 'staff', 'staff_observer', 'staff_reporting_relationships', 'staff_manager']
dimensions: ['staff_observation_key', 'teacher_staff_key', 'observer_staff_key', 'location_key', 'term_key', 'observed_date_key', 'observed_timestamp', 'academic_year', 'score', 'overall_rating', 'notes', 'positive_feedback', 'growth_areas', 'is_locked']
measures: ['count_observations', '_sum_score', '_count_scored', 'avg_score', 'count_overall_rating_1', 'count_overall_rating_2', 'count_overall_rating_3', 'count_overall_rating_4']
pii dims: ['teacher_staff_key', 'observer_staff_key', 'score', 'overall_rating', 'notes', 'positive_feedback', 'growth_areas']
```

- [ ] **Step 3: Run schema test on the new file**

```bash
uv run pytest tests/cube/test_cube_schema.py -v -k "staff_observations"
```

Expected: PASS (cube name is `staff_observations`, no `dim_`/`fct_` prefix).

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_observations.yml
git commit -m "feat(cube): add staff_observations fact cube with teacher/observer/manager join paths"
```

---

## Task 5: `staff_observations_detail.yml` — detail view

Detail view over `staff_observations`. Exposes individual-record dimensions
including both staff keys plus the full join path through teacher staff,
observer staff, manager staff, dates, location, terms, and reporting
relationships. Implements Pattern 5: two access policy tiers.

**Access policy (Pattern 5):**

- `group: detail-access` — base tier; includes all fields EXCEPT the seven
  observation content fields (`score`, `overall_rating`, `notes`,
  `positive_feedback`, `growth_areas`) and all staff PII fields from the three
  staff join paths (teacher `staff_*`, observer `staff_observer_*`, manager
  `staff_manager_*`).
- `group: cube-access-staff-observations` — unlocks the observation content
  fields.
- `group: cube-access-staff-pii` — unlocks staff PII fields from all three join
  paths.

The three access policy entries are additive. A user with `detail-access` only
sees metadata dimensions and measures. A user with both `detail-access` and
`cube-access-staff-observations` sees observation content. A user with
`detail-access` and `cube-access-staff-pii` sees teacher, observer, and manager
name/contact fields. All three groups are needed for full access.

Row-level scoping is handled by `queryRewrite` in `cube.js` (injects
`locations.abbreviation IN (...)` or `locations.region_key = ...` based on the
user's Google group scope) — no observations-specific mechanism is needed here.

**`prefix: true` naming:** all join paths use `prefix: true`. Post-prefix member
names are the join path's last segment prepended to the field name. Examples:

- `join_path: staff_observations.staff` with `prefix: true` → `staff_full_name`,
  `staff_staff_key`
- `join_path: staff_observations.staff_observer` with `prefix: true` →
  `staff_observer_full_name`
- `join_path: staff_observations.staff_manager` with `prefix: true` →
  `staff_manager_full_name`

The `excludes:` list in `access_policy` must use these post-prefix names.

**Files:**

- Create: `src/cube/model/views/staff/staff_observations_detail.yml`

- [ ] **Step 1: Create `src/cube/model/views/staff/` directory if it does not
      exist**

```bash
ls src/cube/model/views/staff/ 2>/dev/null || mkdir -p src/cube/model/views/staff/
```

- [ ] **Step 2: Write `staff_observations_detail.yml`**

```yaml
views:
  - name: staff_observations_detail
    description: >-
      Row-level staff observation records. One row per observation event. Use
      for drill-down into individual observation scores, feedback, and ratings.
      For aggregate analysis (observation counts, average scores by school or
      teacher), use staff_observations_summary instead.

      Access is two-tiered. Base access (detail-access) exposes observation
      metadata — date, location, term, academic year, locked status, and count
      measures — but not observation content fields (score, overall_rating,
      notes, positive_feedback, growth_areas). The
      cube-access-staff-observations group unlocks observation content. Staff
      PII fields (names, emails, etc.) for teacher, observer, and manager
      require cube-access-staff-pii.

      Row-level location scoping is enforced by queryRewrite in cube.js — users
      see only observations at schools within their Google group scope. No
      observations-specific filter is needed.

      pct_evaluated and pct_assigned_goals are not available — blocked on issue
      #3839 (is_teaching_role flag missing from dim_staff_work_assignments).

    cubes:
      - join_path: staff_observations
        includes:
          - count_observations
          - avg_score
          - count_overall_rating_1
          - count_overall_rating_2
          - count_overall_rating_3
          - count_overall_rating_4
          - observed_date_key
          - observed_timestamp
          - academic_year
          - score
          - overall_rating
          - notes
          - positive_feedback
          - growth_areas
          - is_locked

      - join_path: staff_observations.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name
          - month_number
          - quarter_number
          - school_week_start_date
          - is_weekday

      - join_path: staff_observations.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: staff_observations.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: staff_observations.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: staff_observations.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - google_email
          - active_directory_username
          - staff_unique_id
          - gender_identity
          - race
          - is_hispanic

      - join_path: staff_observations.staff_observer
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - google_email
          - active_directory_username
          - staff_unique_id

      - join_path: staff_observations.staff_manager
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - google_email
          - active_directory_username
          - staff_unique_id

    meta:
      folders:
        - name: Observation
          members:
            - observed_date_key
            - observed_timestamp
            - academic_year
            - score
            - overall_rating
            - notes
            - positive_feedback
            - growth_areas
            - is_locked
        - name: Measures
          members:
            - count_observations
            - avg_score
            - count_overall_rating_1
            - count_overall_rating_2
            - count_overall_rating_3
            - count_overall_rating_4
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name
            - dates_month_number
            - dates_quarter_number
            - dates_school_week_start_date
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
        - name: Teacher
          members:
            - staff_staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
            - staff_active_directory_username
            - staff_staff_unique_id
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
        - name: Observer
          members:
            - staff_observer_staff_key
            - staff_observer_full_name
            - staff_observer_first_name
            - staff_observer_last_name
            - staff_observer_work_email
            - staff_observer_google_email
            - staff_observer_active_directory_username
            - staff_observer_staff_unique_id
        - name: Manager (at observation date)
          members:
            - staff_manager_staff_key
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
            - staff_manager_google_email
            - staff_manager_active_directory_username
            - staff_manager_staff_unique_id

    access_policy:
      # Tier 1: base detail access — observation metadata only.
      # Excludes observation content fields (Pattern 5 column gate) and
      # all staff PII from teacher, observer, and manager join paths (Pattern 1).
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            # Observation content fields (Pattern 5)
            - score
            - overall_rating
            - notes
            - positive_feedback
            - growth_areas
            # Teacher staff PII (Pattern 1, prefix: staff_)
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_google_email
            - staff_active_directory_username
            - staff_staff_unique_id
            # Observer staff PII (Pattern 1, prefix: staff_observer_)
            - staff_observer_full_name
            - staff_observer_first_name
            - staff_observer_last_name
            - staff_observer_work_email
            - staff_observer_google_email
            - staff_observer_active_directory_username
            - staff_observer_staff_unique_id
            # Manager staff PII (Pattern 1, prefix: staff_manager_)
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
            - staff_manager_google_email
            - staff_manager_active_directory_username
            - staff_manager_staff_unique_id
      # Tier 2: unlocks observation content fields for authorized users.
      # Row-level scoping is handled by queryRewrite in cube.js — no
      # observations-specific filter is needed here.
      - group: cube-access-staff-observations
        member_level:
          includes: "*"
      # Tier 3: unlocks staff PII across teacher, observer, and manager paths.
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/staff/staff_observations_detail.yml').read_text())
view = data['views'][0]
print('name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
excludes = view['access_policy'][0]['member_level']['excludes']
print('detail-access excludes count:', len(excludes))
print('detail-access excludes:', excludes)
"
```

Expected output:

```text
name: staff_observations_detail
join paths: ['staff_observations', 'staff_observations.dates', 'staff_observations.locations', 'staff_observations.locations.regions', 'staff_observations.terms', 'staff_observations.staff', 'staff_observations.staff_observer', 'staff_observations.staff_manager']
access groups: ['detail-access', 'cube-access-staff-observations', 'cube-access-staff-pii']
detail-access excludes count: 26
detail-access excludes: ['score', 'overall_rating', 'notes', 'positive_feedback', 'growth_areas', 'staff_full_name', 'staff_first_name', 'staff_last_name', 'staff_work_email', 'staff_google_email', 'staff_active_directory_username', 'staff_staff_unique_id', 'staff_observer_full_name', 'staff_observer_first_name', 'staff_observer_last_name', 'staff_observer_work_email', 'staff_observer_google_email', 'staff_observer_active_directory_username', 'staff_observer_staff_unique_id', 'staff_manager_full_name', 'staff_manager_first_name', 'staff_manager_last_name', 'staff_manager_work_email', 'staff_manager_google_email', 'staff_manager_active_directory_username', 'staff_manager_staff_unique_id']
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/staff_observations_detail.yml
git commit -m "feat(cube): add staff_observations_detail view with Pattern 5 access policy"
```

---

## Task 6: `staff_observations_summary.yml` — summary view

Summary view over `staff_observations`. No individual identifiers — no staff
keys, no teacher or observer names, no observation free-text fields. Exposes
only aggregate measures and grouping dimensions (location, term, academic year,
date, school). Single access policy block gating on `summary-access`.

`date_day` is included for time-series analysis (week-over-week score trends,
observation count by month) — this is a core consumer need even at the summary
level per the spec.

`gender_identity`, `race`, and `is_hispanic` from the teacher staff join are
included as aggregate breakdowns — they are categorical demographic dimensions
visible at base access and not in the `excludes:` list. These carry
`meta: {pii: true}` on the cube dimension but are included in the summary view
for trend analysis (same as student attendance summary includes `race`,
`gender_identity`).

**Files:**

- Create: `src/cube/model/views/staff/staff_observations_summary.yml`

- [ ] **Step 1: Write `staff_observations_summary.yml`**

```yaml
views:
  - name: staff_observations_summary
    description: >-
      Aggregated staff observations for observation count, average score, and
      rating distribution breakdowns. No individual teacher identifiers or
      observation content fields. Use for school-level or network-level
      dashboards showing observation cadence and score trends. For individual
      observation records, scores, or feedback, use staff_observations_detail.

      pct_evaluated and pct_assigned_goals are not available — blocked on issue
      #3839 (is_teaching_role flag missing from dim_staff_work_assignments).

    cubes:
      - join_path: staff_observations
        includes:
          - count_observations
          - avg_score
          - count_overall_rating_1
          - count_overall_rating_2
          - count_overall_rating_3
          - count_overall_rating_4
          - academic_year
          - overall_rating
          - is_locked

      - join_path: staff_observations.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name
          - month_number
          - quarter_number
          - school_week_start_date

      - join_path: staff_observations.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: staff_observations.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: staff_observations.terms
        prefix: true
        includes:
          - academic_year
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: staff_observations.staff
        prefix: true
        includes:
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Measures
          members:
            - count_observations
            - avg_score
            - count_overall_rating_1
            - count_overall_rating_2
            - count_overall_rating_3
            - count_overall_rating_4
        - name: Observation
          members:
            - academic_year
            - overall_rating
            - is_locked
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name
            - dates_month_number
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
        - name: Teacher (demographics)
          members:
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic

    access_policy:
      # No PII tier — view contains no direct staff identifiers or
      # observation content fields. Demographic dimensions (race,
      # gender_identity, is_hispanic) are aggregate breakdowns only.
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/staff/staff_observations_summary.yml').read_text())
view = data['views'][0]
print('name:', view['name'])
print('join paths:', [c['join_path'] for c in view['cubes']])
print('access groups:', [p['group'] for p in view['access_policy']])
"
```

Expected output:

```text
name: staff_observations_summary
join paths: ['staff_observations', 'staff_observations.dates', 'staff_observations.locations', 'staff_observations.locations.regions', 'staff_observations.terms', 'staff_observations.staff']
access groups: ['summary-access']
```

- [ ] **Step 3: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all tests PASS including `test_cube_schema.py` parametrized cases for
all new staff observation files.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/staff_observations_summary.yml
git commit -m "feat(cube): add staff_observations_summary view"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate the changes in Cube Cloud Dev
Mode. Dev Mode (per-developer branch endpoint) is the only environment where
server `console.log` output is visible — staging has no log UI. Add the branch
by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["staff_observations_summary.count_observations"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string containing `fct_staff_observations` as the FROM table and
`count(distinct staff_observations.staff_observation_key)` or equivalent in the
SELECT.

**Check 2 — All five new view/cube names appear in `meta`:**

Call the Cube MCP `meta` tool. Expected to find in the response:
`staff_observations_detail`, `staff_observations_summary`. The four cube files
(`staff_observations`, `staff_observer`, `staff_reporting_relationships`,
`staff_manager`) should NOT appear (all are `public: false`).

**Check 3 — Pattern 5 column gate works:**

Compile a query requesting `score` with a `detail-access`-only user (no
`cube-access-staff-observations`). The response should return an "access denied"
or empty field list for the observation content fields. With
`cube-access-staff-observations`, `score` should appear in the compiled SQL.

```bash
# Without cube-access-staff-observations — score should be absent
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-detail-only>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["staff_observations_detail.score"],"limit":1}}' \
  | jq '.error // .sql'

# With cube-access-staff-observations — score should appear
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-with-observations>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["staff_observations_detail.score"],"limit":1}}' \
  | jq '.sql'
```

**Check 4 — Row-level scoping (queryRewrite):**

Compile a query with a school-scoped user (e.g., `cube-school-bold-detail`). The
compiled SQL should contain `locations.abbreviation IN ('bold')` or equivalent
injected by `queryRewrite`. This applies to observations the same as any other
domain — no observations-specific check needed beyond confirming the standard
location filter fires.

**Check 5 — Observer join resolves correctly:**

Compile a query requesting `staff_observer_full_name` alongside
`staff_full_name` with a user who has both `cube-access-staff-observations` and
`cube-access-staff-pii`. The SQL should show two separate `dim_staff` joins —
one aliased to the teacher role, one to the observer role — confirming the
`extends: staff` role alias pattern works as expected.

**Check 6 — Manager resolver zero fan-out:**

Run a load query grouping by `staff_manager_full_name` and `count_observations`.
Verify the total `count_observations` in this query matches the
`count_observations` in a query without the manager breakdown (same
date/location filter). A mismatch indicates fan-out in the
`staff_reporting_relationships` join — the BETWEEN join plus the prod-validated
no-overlap invariant should prevent this. The 48 observations pre-dating the
teacher's primary/reporting span correctly resolve to NULL manager (LEFT JOIN
behavior).
