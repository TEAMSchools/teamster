> **Measures: not implemented in this pass.** Skip all `measures:` sections when
> writing cube files — dimensions, joins, and `public: false` only. Remove
> measure names from view `includes:` lists (keep dimension names only). Add
> measures on demand as analysts request specific aggregations.

# Cube Staff Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the five cube files and two view files that comprise the Staff
Core domain in the Cube semantic layer, covering `dim_staff`, the SCD2
period-intersection employment history cube, the point-in-time manager resolver,
and the `staff_manager` role alias, then expose them through `staff_detail` and
`staff_summary` views.

**Prerequisite:** Plan 0 (`2026-06-01-cube-model-yaml-implementation.md`) must
run first — the conformed cube renames (`dates`, `locations`, `regions`) and the
`cube.js` helper changes (`isStaffMember`, `withSyntheticGroups`) that this plan
depends on must already be in place.

**Architecture:** Five cube files in `src/cube/model/cubes/staff/` and two view
files in `src/cube/model/views/staff/`. All cubes `public: false`; views expose
members explicitly. `staff_work_history` uses Pattern 3 (SCD2 period
intersection via `sql:` with GREATEST/LEAST). `staff_reporting_relationships` is
a helper cube used by per-fact joins on fact cubes that need point-in-time
manager resolution — it is not included in the staff views. `staff_manager` is a
three-line role alias extending `staff`. All cubes are automatically covered by
`isStaffMember` in `queryRewrite` because their names start with `staff`.

**Tech Stack:** Cube YAML (`src/cube/model/`), Python (`pytest`, `pyyaml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Column name corrections from dbt property file verification

The spec's Pattern 3 reference YAML was written before final dbt column names
were confirmed. Two corrections apply before writing any files:

**`dim_work_assignment_locations`** — The actual column is `location_key` (FK to
`dim_locations`), not `location_code`. The spec text says "location join gap —
`location_code` as string dimension." That gap is resolved: the column IS a
`location_key` FK. The `staff_work_history` SQL should join
`dim_work_assignment_locations` on
`wl.work_assignment_key = swa.work_assignment_key` (with date overlap) and
expose `wl.location_key AS work_location_key`. A `locations` join can now be
declared on `staff_work_history` via this FK.

**`dim_work_assignment_organizational_units`** — The `assignment_type` column
values are `'home'` and `'assigned'` (not `'Primary'`). The spec's SQL uses
`AND wo.assignment_type = 'Primary'` — the correct filter to isolate the primary
org unit row is `AND wo.assignment_type = 'home'`.

**`dim_work_assignment_types`** — The worker type column is `worker_type_name`
(confirmed). The spec alias `wt.worker_type_name AS worker_type` in the SELECT
is correct. In the cube dimension, `sql: worker_type` references the SELECT
alias, so the dimension name `worker_type` is fine.

---

## Files

| File                                                           | Action |
| -------------------------------------------------------------- | ------ |
| `src/cube/model/cubes/staff/staff.yml`                         | Create |
| `src/cube/model/cubes/staff/staff_work_history.yml`            | Create |
| `src/cube/model/cubes/staff/staff_reporting_relationships.yml` | Create |
| `src/cube/model/cubes/staff/staff_manager.yml`                 | Create |
| `src/cube/model/views/staff/staff_detail.yml`                  | Create |
| `src/cube/model/views/staff/staff_summary.yml`                 | Create |

---

## Task 1: Schema validation test extension

Extend the existing `tests/cube/test_cube_schema.py` to validate the new staff
cube files when they are created. No changes to the test file are needed — it
already uses `rglob("*.yml")` to discover all cube files and will pick up the
new `staff/` directory automatically. Run the test at the end of each cube task
to verify no `dim_` or `fct_` prefix was accidentally introduced.

- [ ] **Step 1: Confirm existing test covers the new directory**

```bash
uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -5
```

Expected: all existing tests PASS (Plan 0 complete prerequisite).

---

## Task 2: Create `staff/staff.yml` — thin wrapper on `dim_staff`

Pattern 1 shape: `sql_table:` pointing at `kipptaf_marts.dim_staff`. No `joins:`
— other cubes join to `staff` on their side. No `measures:`. PII fields tagged
with `meta: {pii: true}`. Sensitive demographics (`gender_identity`, `race`,
`is_hispanic`) are visible at base access level and tagged `meta: {pii: true}`
but not in any `excludes:` list.

**Files:**

- Create: `src/cube/model/cubes/staff/staff.yml`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p src/cube/model/cubes/staff
```

- [ ] **Step 2: Write `staff.yml`**

Write the following as the complete content of
`src/cube/model/cubes/staff/staff.yml`:

```yaml
cubes:
  - name: staff
    public: false
    sql_table: kipptaf_marts.dim_staff

    dimensions:
      - name: staff_key
        sql: staff_key
        type: string
        primary_key: true

      - name: staff_unique_id
        sql: staff_unique_id
        type: number
        public: true
        meta:
          pii: true

      - name: full_name
        sql: full_name
        type: string
        public: true
        meta:
          pii: true

      - name: first_name
        sql: first_name
        type: string
        public: true
        meta:
          pii: true

      - name: last_name
        sql: last_name
        type: string
        public: true
        meta:
          pii: true

      - name: birth_date
        sql: CAST(birth_date AS TIMESTAMP)
        type: time
        public: true
        meta:
          pii: true

      - name: gender_identity
        sql: gender_identity
        type: string
        public: true
        meta:
          pii: true

      - name: race
        sql: race
        type: string
        public: true
        meta:
          pii: true

      - name: is_hispanic
        sql: is_hispanic
        type: boolean
        public: true
        meta:
          pii: true

      - name: work_email
        sql: work_email
        type: string
        public: true
        meta:
          pii: true

      - name: personal_email
        sql: personal_email
        type: string
        public: true
        meta:
          pii: true

      - name: personal_cell_phone
        sql: personal_cell_phone
        type: string
        public: true
        meta:
          pii: true

      - name: active_directory_username
        sql: active_directory_username
        type: string
        public: true
        meta:
          pii: true

      - name: google_email
        sql: google_email
        type: string
        public: true
        meta:
          pii: true

      - name: original_hire_date
        sql: CAST(original_hire_date AS TIMESTAMP)
        type: time
        public: true

      - name: rehire_date
        sql: CAST(rehire_date AS TIMESTAMP)
        type: time
        public: true
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('dimension count:', len(cube['dimensions']))
pii_dims = [d['name'] for d in cube['dimensions'] if d.get('meta', {}).get('pii')]
print('pii dimensions:', pii_dims)
"
```

Expected output:

```text
cube name: staff
public: False
dimension count: 17
pii dimensions: ['staff_unique_id', 'full_name', 'first_name', 'last_name', 'birth_date', 'gender_identity', 'race', 'is_hispanic', 'work_email', 'personal_email', 'personal_cell_phone', 'active_directory_username', 'google_email']
```

- [ ] **Step 4: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS including `staff/staff.yml`.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/staff/staff.yml
git commit -m "feat(cube): add staff cube — dim_staff thin wrapper (Pattern 1)"
```

---

## Task 3: Create `staff/staff_work_history.yml` — SCD2 period intersection

Pattern 3 shape: `sql:` with explicit column list, GREATEST/LEAST date
intersection across five SCD2 children (`dim_staff_status`,
`dim_work_assignment_jobs`, `dim_work_assignment_types`,
`dim_work_assignment_organizational_units`, `dim_work_assignment_locations`).
`dim_work_assignment_primary` is LEFT JOINed; its date columns are excluded from
GREATEST/LEAST. A `dates` join uses `relationship: one_to_many` (one employment
period spans many dates). A `staff` join enables view traversal to the `staff`
dim. A `locations` join is now enabled via the `work_location_key` column that
was verified against `dim_work_assignment_locations.location_key`.

**Corrections from dbt property file verification applied here:**

- `wl.location_code AS work_location_code` →
  `wl.location_key AS work_location_key`
- `AND wo.assignment_type = 'Primary'` → `AND wo.assignment_type = 'home'`

**Files:**

- Create: `src/cube/model/cubes/staff/staff_work_history.yml`

- [ ] **Step 1: Write `staff_work_history.yml`**

Write the following as the complete content of
`src/cube/model/cubes/staff/staff_work_history.yml`:

```yaml
cubes:
  - name: staff_work_history
    public: false
    sql: |
      SELECT
        swa.work_assignment_key,
        swa.staff_key,
        swa.full_time_equivalency,
        swa.is_management_position,
        ss.status_name,
        wj.position_title,
        wj.job_code,
        wt.worker_type_name            AS worker_type,
        wo.department_name,
        wo.business_unit_name,
        wl.location_key                AS work_location_key,
        wp.is_primary_position,
        comp.annual_wage,
        comp.hourly_wage,
        comp.daily_rate,
        comp.period_rate,
        GREATEST(
          ss.effective_start_date,
          wj.effective_start_date,
          wt.effective_start_date,
          wo.effective_start_date,
          wl.effective_start_date,
          COALESCE(comp.effective_start_date_key, DATE '1900-01-01')
        ) AS effective_start_date,
        LEAST(
          ss.effective_end_date,
          wj.effective_end_date,
          wt.effective_end_date,
          wo.effective_end_date,
          wl.effective_end_date,
          COALESCE(comp.effective_end_date_key, DATE '9999-12-31')
        ) AS effective_end_date
      FROM kipptaf_marts.dim_staff_work_assignments swa
      JOIN kipptaf_marts.dim_staff_status ss
        ON ss.staff_key = swa.staff_key
      JOIN kipptaf_marts.dim_work_assignment_jobs wj
        ON wj.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wj.effective_end_date
        AND ss.effective_end_date   > wj.effective_start_date
      JOIN kipptaf_marts.dim_work_assignment_types wt
        ON wt.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wt.effective_end_date
        AND ss.effective_end_date   > wt.effective_start_date
      JOIN kipptaf_marts.dim_work_assignment_organizational_units wo
        ON wo.work_assignment_key = swa.work_assignment_key
        AND wo.assignment_type = 'home'
        AND ss.effective_start_date < wo.effective_end_date
        AND ss.effective_end_date   > wo.effective_start_date
      JOIN kipptaf_marts.dim_work_assignment_locations wl
        ON wl.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wl.effective_end_date
        AND ss.effective_end_date   > wl.effective_start_date
      LEFT JOIN kipptaf_marts.dim_work_assignment_primary wp
        ON wp.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < wp.effective_end_date
        AND ss.effective_end_date   > wp.effective_start_date
      -- Compensation is LEFT JOIN — some assignments have no comp record
      -- (contractors, volunteers). COALESCE in GREATEST/LEAST above ensures
      -- null comp dates don't collapse the intersection for uncompensated rows.
      -- One comp row per assignment per period (no earning_item_id in PK), so
      -- no fan-out risk from this join.
      LEFT JOIN kipptaf_marts.fct_work_assignment_compensation comp
        ON comp.work_assignment_key = swa.work_assignment_key
        AND ss.effective_start_date < comp.effective_end_date_key
        AND ss.effective_end_date   > comp.effective_start_date_key

    joins:
      - name: dates
        sql: >
          {dates.date_day} BETWEEN CAST({CUBE}.effective_start_date AS
          TIMESTAMP) AND CAST({CUBE}.effective_end_date AS TIMESTAMP)
        relationship: one_to_many

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.staff_key"
        relationship: many_to_one

      - name: locations
        sql: "{locations.location_key} = {CUBE}.work_location_key"
        relationship: many_to_one

      # Point-in-time manager resolver. many_to_one is safe only when a date
      # filter is applied — without one, multiple work-history periods per
      # person each match their contemporaneous reporting relationship row,
      # which is correct. Without a date filter, the join is effectively
      # many_to_many. Always apply a date filter on staff_work_history queries.
      - name: staff_reporting_relationships
        sql: >
          {staff_reporting_relationships.staff_key} = {CUBE}.staff_key AND
          CAST({CUBE}.effective_start_date AS TIMESTAMP)
            <= {staff_reporting_relationships.effective_end_date} AND
          CAST({CUBE}.effective_end_date AS TIMESTAMP)
            >= {staff_reporting_relationships.effective_start_date}
        relationship: many_to_one

      - name: staff_manager
        sql: >
          {staff_manager.staff_key} =
          {staff_reporting_relationships.manager_staff_key}
        relationship: many_to_one

    dimensions:
      - name: staff_work_history_key
        sql: >
          CONCAT(
            CAST({CUBE}.staff_key AS STRING), '|',
            CAST({CUBE}.effective_start_date AS STRING)
          )
        type: string
        primary_key: true

      - name: status_name
        sql: status_name
        type: string
        public: true

      - name: position_title
        sql: position_title
        type: string
        public: true

      - name: job_code
        sql: job_code
        type: string
        public: true

      - name: worker_type
        sql: worker_type
        type: string
        public: true

      - name: department_name
        sql: department_name
        type: string
        public: true

      - name: business_unit_name
        sql: business_unit_name
        type: string
        public: true

      - name: work_location_key
        sql: work_location_key
        type: string
        public: true

      - name: is_primary_position
        sql: is_primary_position
        type: boolean
        public: true

      - name: is_management_position
        sql: is_management_position
        type: boolean
        public: true

      - name: full_time_equivalency
        sql: full_time_equivalency
        type: number
        public: true

      - name: effective_start_date
        sql: CAST(effective_start_date AS TIMESTAMP)
        type: time
        public: true

      # Compensation fields — gated by cube-access-staff-compensation in views.
      # Null for uncompensated assignments (contractors, volunteers).
      - name: annual_wage
        sql: annual_wage
        type: number
        public: true
        meta:
          pii: true

      - name: hourly_wage
        sql: hourly_wage
        type: number
        public: true
        meta:
          pii: true

      - name: daily_rate
        sql: daily_rate
        type: number
        public: true
        meta:
          pii: true

      - name: period_rate
        sql: period_rate
        type: number
        public: true
        meta:
          pii: true

      - name: sum_fte
        description: Total FTE of active assignments
        sql: full_time_equivalency
        type: sum
        public: true
        filters:
          - sql: "{CUBE}.status_name = 'Active'"

      - name: avg_annual_wage
        description: Average annual wage across assignments in scope
        sql: annual_wage
        type: avg
        public: true

      - name: avg_hourly_wage
        description: Average hourly wage — null for salaried assignments
        sql: hourly_wage
        type: avg
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_work_history.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
join_names = [j['name'] for j in cube['joins']]
print('joins:', join_names)
dim_names = [d['name'] for d in cube['dimensions']]
print('dimensions:', dim_names)
measure_names = [m['name'] for m in cube['measures']]
print('measures:', measure_names)
dates_join = next(j for j in cube['joins'] if j['name'] == 'dates')
print('dates relationship:', dates_join['relationship'])
"
```

Expected output:

```text
cube name: staff_work_history
public: False
joins: ['dates', 'staff', 'locations']
dimensions: ['staff_work_history_key', 'status_name', 'position_title', 'job_code', 'worker_type', 'department_name', 'business_unit_name', 'work_location_key', 'is_primary_position', 'is_management_position', 'full_time_equivalency', 'effective_start_date', 'annual_wage', 'hourly_wage', 'daily_rate', 'period_rate']
measures: ['count_headcount', 'sum_fte', 'avg_annual_wage', 'avg_hourly_wage']
dates relationship: one_to_many
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_work_history.yml
git commit -m "feat(cube): add staff_work_history cube — SCD2 period intersection (Pattern 3)"
```

---

## Task 4: Create `staff/staff_reporting_relationships.yml` — point-in-time manager resolver

Helper cube used by fact cubes that need point-in-time manager resolution.
`public: false`. SQL is validated against prod (2026-05-28 per spec). Three
dimensions: a composite PK, `staff_key` (the reportee), and `manager_staff_key`
(the manager FK). One time dimension `effective_start_date` for the join. No
`measures:`.

This cube is NOT exposed in `staff_detail` or `staff_summary` views — it is a
join helper for per-fact cubes (observations, gradebook, surveys). Its inclusion
here makes it available for those future joins without requiring a separate PR.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_reporting_relationships.yml`

- [ ] **Step 1: Write `staff_reporting_relationships.yml`**

Write the following as the complete content of
`src/cube/model/cubes/staff/staff_reporting_relationships.yml`:

```yaml
cubes:
  - name: staff_reporting_relationships
    public: false
    sql: |
      SELECT
        swa.staff_key,
        rr.manager_staff_key,
        GREATEST(wap.effective_start_date, rr.effective_start_date) AS effective_start_date,
        LEAST(wap.effective_end_date,      rr.effective_end_date)   AS effective_end_date
      FROM kipptaf_marts.dim_work_assignment_primary wap
      JOIN kipptaf_marts.dim_staff_work_assignments swa
        ON wap.work_assignment_key = swa.work_assignment_key
        AND swa.staff_key IS NOT NULL
      JOIN kipptaf_marts.dim_work_assignment_reporting_relationships rr
        ON rr.work_assignment_key = wap.work_assignment_key
        AND wap.effective_start_date <= rr.effective_end_date
        AND wap.effective_end_date   >= rr.effective_start_date
      WHERE wap.is_primary_position

    dimensions:
      - name: staff_reporting_relationship_key
        sql: >
          CONCAT(
            CAST({CUBE}.staff_key AS STRING), '|',
            CAST({CUBE}.effective_start_date AS STRING)
          )
        type: string
        primary_key: true

      - name: staff_key
        sql: staff_key
        type: string
        public: true

      - name: manager_staff_key
        sql: manager_staff_key
        type: string
        public: true

      - name: effective_start_date
        sql: CAST(effective_start_date AS TIMESTAMP)
        type: time
        public: true

      # effective_end_date is required by the per-fact BETWEEN join condition
      # used in staff_observations and other fact cubes that resolve
      # point-in-time manager:
      #   CAST({CUBE}.date_key AS TIMESTAMP)
      #     BETWEEN {staff_reporting_relationships.effective_start_date}
      #     AND     {staff_reporting_relationships.effective_end_date}
      - name: effective_end_date
        sql: CAST(effective_end_date AS TIMESTAMP)
        type: time
        public: true
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_reporting_relationships.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('public:', cube.get('public'))
print('has joins:', 'joins' in cube)
dim_names = [d['name'] for d in cube['dimensions']]
print('dimensions:', dim_names)
pk = next(d for d in cube['dimensions'] if d.get('primary_key'))
print('primary key:', pk['name'])
"
```

Expected output:

```text
cube name: staff_reporting_relationships
public: False
has joins: False
dimensions: ['staff_reporting_relationship_key', 'staff_key', 'manager_staff_key', 'effective_start_date', 'effective_end_date']
primary key: staff_reporting_relationship_key
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_reporting_relationships.yml
git commit -m "feat(cube): add staff_reporting_relationships cube — point-in-time manager resolver"
```

---

## Task 5: Create `staff/staff_manager.yml` — role alias

Three lines: name, extends, public. No additional SQL, no dimensions, no
measures. Inherits everything from `staff`. `staff_` prefix keeps it under
`isStaffMember` in `queryRewrite`. Used as a join target on fact cubes that have
a secondary manager FK (observations, gradebook, surveys). Not exposed in views.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_manager.yml`

- [ ] **Step 1: Write `staff_manager.yml`**

Write the following as the complete content of
`src/cube/model/cubes/staff/staff_manager.yml`:

```yaml
cubes:
  - name: staff_manager
    extends: staff
    public: false
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_manager.yml').read_text())
cube = data['cubes'][0]
print('cube name:', cube['name'])
print('extends:', cube.get('extends'))
print('public:', cube.get('public'))
print('extra keys:', [k for k in cube if k not in ('name', 'extends', 'public')])
"
```

Expected output:

```text
cube name: staff_manager
extends: staff
public: False
extra keys: []
```

- [ ] **Step 3: Run schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_manager.yml
git commit -m "feat(cube): add staff_manager role alias cube — extends staff"
```

---

## Task 6: Create `views/staff/staff_detail.yml` — detail view

Exposes `staff_work_history` measures and grouping dimensions, date context from
`dates`, staff PII fields from `staff`, and location context from `locations`
(enabled by the `work_location_key` FK on `staff_work_history`). PII fields are
present but hidden from users without `cube-access-staff-pii`.

`prefix: true` on all join path blocks. Access policy: `detail-access` block
with staff PII in `excludes:`, then `cube-access-staff-pii` block with
`includes: "*"` to restore full access. The `excludes:` list uses post-prefix
names (`staff_full_name`, not `full_name`).

**Files:**

- Create: `src/cube/model/views/staff/staff_detail.yml`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p src/cube/model/views/staff
```

- [ ] **Step 2: Write `staff_detail.yml`**

Write the following as the complete content of
`src/cube/model/views/staff/staff_detail.yml`:

```yaml
views:
  - name: staff_detail
    description: >-
      Row-level staff employment history. One row per employee x employment
      period — each row represents a contiguous window when all time-varying
      attributes (status, job, worker type, org unit, location, compensation)
      held simultaneously, with point-in-time manager context via
      staff_reporting_relationships. Use for drill-down, headcount-over-time,
      and individual employee investigations. Always apply a date filter before
      querying — without one, each employment period fans out to one row per
      calendar day in its effective range.

      Primary-position filtering: use is_primary_position = true to isolate the
      employee's primary assignment at a point in time. status_name = 'Active'
      filters to active employees only. Contains direct staff and manager
      identifiers — see access_policy for PII gating.

    cubes:
      - join_path: staff_work_history
        includes:
          - count_headcount
          - sum_fte
          - avg_annual_wage
          - avg_hourly_wage
          - status_name
          - position_title
          - job_code
          - worker_type
          - department_name
          - business_unit_name
          - is_primary_position
          - is_management_position
          - full_time_equivalency
          - effective_start_date
          - annual_wage
          - hourly_wage
          - daily_rate
          - period_rate

      - join_path: staff_work_history.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name
          - month_number
          - year_number

      - join_path: staff_work_history.staff
        prefix: true
        includes:
          - staff_key
          - staff_unique_id
          - full_name
          - first_name
          - last_name
          - birth_date
          - work_email
          - google_email
          - personal_email
          - personal_cell_phone
          - active_directory_username
          - gender_identity
          - race
          - is_hispanic
          - original_hire_date
          - rehire_date

      - join_path: staff_work_history.locations
        prefix: true
        includes:
          - location_name
          - location_abbreviation
          - location_grade_band

      - join_path: staff_work_history.locations.regions
        prefix: true
        includes:
          - region_name

      - join_path: staff_work_history.staff_manager
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email

    meta:
      folders:
        - name: Employment
          members:
            - status_name
            - position_title
            - job_code
            - worker_type
            - department_name
            - business_unit_name
            - is_primary_position
            - is_management_position
            - full_time_equivalency
            - effective_start_date
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name
            - dates_month_number
            - dates_year_number
        - name: Location
          members:
            - locations_location_name
            - locations_location_abbreviation
            - locations_location_grade_band
            - regions_region_name
        - name: Staff
          members:
            - staff_staff_key
            - staff_staff_unique_id
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_birth_date
            - staff_work_email
            - staff_google_email
            - staff_personal_email
            - staff_personal_cell_phone
            - staff_active_directory_username
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
            - staff_original_hire_date
            - staff_rehire_date
        - name: Manager
          members:
            - staff_manager_staff_key
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email

    access_policy:
      # detail-access: excludes staff PII (employee + manager) and compensation.
      # cube-access-staff-pii: full access except compensation.
      # cube-access-staff-compensation: full access except staff PII.
      # A user with both groups sees everything.
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_birth_date
            - staff_work_email
            - staff_google_email
            - staff_personal_email
            - staff_personal_cell_phone
            - staff_active_directory_username
            - staff_staff_unique_id
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
            - annual_wage
            - hourly_wage
            - daily_rate
            - period_rate
            - avg_annual_wage
            - avg_hourly_wage
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
          excludes:
            - annual_wage
            - hourly_wage
            - daily_rate
            - period_rate
            - avg_annual_wage
            - avg_hourly_wage
      - group: cube-access-staff-compensation
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_birth_date
            - staff_work_email
            - staff_google_email
            - staff_personal_email
            - staff_personal_cell_phone
            - staff_active_directory_username
            - staff_staff_unique_id
            - staff_manager_full_name
            - staff_manager_first_name
            - staff_manager_last_name
            - staff_manager_work_email
```

- [ ] **Step 3: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/staff/staff_detail.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
join_paths = [c['join_path'] for c in view['cubes']]
print('join paths:', join_paths)
access_groups = [p['group'] for p in view['access_policy']]
print('access groups:', access_groups)
detail_block = next(p for p in view['access_policy'] if p['group'] == 'detail-access')
print('excluded fields:', detail_block['member_level']['excludes'])
"
```

Expected output:

```text
view name: staff_detail
join paths: ['staff_work_history', 'staff_work_history.dates', 'staff_work_history.staff', 'staff_work_history.locations', 'staff_work_history.locations.regions', 'staff_work_history.staff_manager']
access groups: ['detail-access', 'cube-access-staff-pii', 'cube-access-staff-compensation']
excluded fields: ['staff_full_name', 'staff_first_name', 'staff_last_name', 'staff_birth_date', 'staff_work_email', 'staff_google_email', 'staff_personal_email', 'staff_personal_cell_phone', 'staff_active_directory_username', 'staff_staff_unique_id', 'staff_manager_full_name', 'staff_manager_first_name', 'staff_manager_last_name', 'staff_manager_work_email', 'annual_wage', 'hourly_wage', 'daily_rate', 'period_rate', 'avg_annual_wage', 'avg_hourly_wage']
```

- [ ] **Step 4: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/staff/staff_detail.yml
git commit -m "feat(cube): add staff_detail view — detail access with PII gating"
```

---

## Task 7: Create `views/staff/staff_summary.yml` — summary view

Exposes only measures and grouping dimensions — no individual identifiers, no
staff name, no staff key. `date_day` is included for time-series analysis.
Single access policy block: `summary-access` with `includes: "*"`. No PII tier
needed.

**Files:**

- Create: `src/cube/model/views/staff/staff_summary.yml`

- [ ] **Step 1: Write `staff_summary.yml`**

Write the following as the complete content of
`src/cube/model/views/staff/staff_summary.yml`:

```yaml
views:
  - name: staff_summary
    description: >-
      Aggregated staff employment history for headcount and FTE breakdowns. One
      row per filter slice — never per employee. No direct staff identifiers.
      Demographic dimensions (gender_identity, race, is_hispanic) are aggregate
      breakdowns only. Always apply a date filter before querying — without one,
      each employment period fans out to one row per calendar day in its
      effective range. Use is_primary_position = true to count each employee
      once (their primary assignment); omit to include all assignments.

    cubes:
      - join_path: staff_work_history
        includes:
          - count_headcount
          - sum_fte
          - avg_annual_wage
          - avg_hourly_wage
          - status_name
          - position_title
          - job_code
          - worker_type
          - department_name
          - business_unit_name
          - is_primary_position
          - is_management_position

      - join_path: staff_work_history.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name
          - month_number
          - year_number

      - join_path: staff_work_history.staff
        prefix: true
        includes:
          - gender_identity
          - race
          - is_hispanic

      - join_path: staff_work_history.locations
        prefix: true
        includes:
          - location_name
          - location_abbreviation
          - location_grade_band

      - join_path: staff_work_history.locations.regions
        prefix: true
        includes:
          - region_name

    meta:
      folders:
        - name: Employment
          members:
            - status_name
            - position_title
            - job_code
            - worker_type
            - department_name
            - business_unit_name
            - is_primary_position
            - is_management_position
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name
            - dates_month_number
            - dates_year_number
        - name: Location
          members:
            - locations_location_name
            - locations_location_abbreviation
            - locations_location_grade_band
            - regions_region_name
        - name: Staff
          members:
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic

    access_policy:
      # summary-access: base gate — excludes compensation fields.
      # cube-access-staff-compensation: unlocks wage averages.
      - group: summary-access
        member_level:
          includes: "*"
          excludes:
            - avg_annual_wage
            - avg_hourly_wage
      - group: cube-access-staff-compensation
        member_level:
          includes: "*"
```

- [ ] **Step 2: Verify the YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/views/staff/staff_summary.yml').read_text())
view = data['views'][0]
print('view name:', view['name'])
join_paths = [c['join_path'] for c in view['cubes']]
print('join paths:', join_paths)
access_groups = [p['group'] for p in view['access_policy']]
print('access groups:', access_groups)
# Verify no staff identifiers are included
all_includes = []
for c in view['cubes']:
    all_includes.extend(c.get('includes', []))
pii_fields = {'staff_key', 'full_name', 'first_name', 'last_name', 'work_email',
              'google_email', 'personal_email', 'personal_cell_phone',
              'active_directory_username', 'staff_unique_id', 'birth_date'}
exposed_pii = pii_fields.intersection(set(all_includes))
print('exposed PII fields (should be empty):', exposed_pii)
"
```

Expected output:

```text
view name: staff_summary
join paths: ['staff_work_history', 'staff_work_history.dates', 'staff_work_history.staff', 'staff_work_history.locations', 'staff_work_history.locations.regions']
access groups: ['summary-access']
exposed PII fields (should be empty): set()
```

- [ ] **Step 3: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/staff_summary.yml
git commit -m "feat(cube): add staff_summary view — summary access, no PII"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate the changes in Cube Cloud Dev
Mode. Dev Mode is the only environment where server `console.log` output is
visible. Add the branch by name in Cube Cloud → Data Model → Dev Mode.

**Check 1 — Model loads:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["staff_summary.count_headcount"],"limit":1}}' \
  | jq '.sql'
```

Expected: a SQL string containing `dim_staff_work_assignments` in the FROM
clause and the GREATEST/LEAST period intersection.

**Check 2 — Views are registered:**

The Cube MCP `meta` tool should list `staff_detail` and `staff_summary` as
available views. `staff_work_history`, `staff`, `staff_reporting_relationships`,
and `staff_manager` should not appear in `meta` (all `public: false`).

**Check 3 — `one_to_many` relationship compiles correctly:**

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "query":{
      "measures":["staff_summary.count_headcount"],
      "timeDimensions":[{
        "dimension":"staff_summary.dates_date_day",
        "dateRange":["2025-11-01","2025-11-01"]
      }],
      "limit":1
    }
  }' \
  | jq '.sql'
```

Expected: SQL contains a `BETWEEN` join from `dim_dates` to the effective date
range columns, not an equality join.

**Check 4 — Security gate works (staff PII hidden from `detail-access`):**

Compile a query for a user with `detail-access` but without
`cube-access-staff-pii` — the `staff_full_name` and other excluded fields should
not appear in the resolved member set.

**Check 5 — `isStaffMember` gate applies:**

Compile a query for a user without any scope group — the SQL should contain
`WHERE (1 = 0)`.

```bash
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-for-user-with-no-scope-group>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"measures":["staff_summary.count_headcount"],"limit":1}}' \
  | jq '.sql' | grep -c "1 = 0"
```

Expected: `1`.
