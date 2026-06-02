# Cube Staff HR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Cube semantic layer coverage for the Staff HR domain — attrition,
compensation, benefits, additional earnings, and staffing positions. Produces
five cube files and up to ten view files (one detail + one summary per cube that
has a standalone consumer grain).

**Architecture:** All cubes live under `src/cube/model/cubes/staff/`; views
under `src/cube/model/views/staff/`. All cubes set `public: false`; the `staff_`
prefix on every cube name ensures automatic `isStaffMember` gate in
`queryRewrite`. Compensation fields are gated by Pattern 2
(`cube-access-staff-compensation`); benefits fields by Pattern 4
(`cube-access-staff-benefits`); staff PII fields (names, contact, identifiers)
by Pattern 1 (`cube-access-staff-pii`).

**Prerequisite:** The Staff Core plan
(`2026-06-01-cube-staff-core-implementation.md`) must be fully merged before
this plan runs. `staff.yml` (the `staff` cube backed by `dim_staff`) and
`staff_work_history.yml` (the period-intersection cube backed by
`dim_staff_work_assignments` + SCD2 children) must already exist for the
`staff_attrition` cube's `staff` join and for the views' `staff_work_history`
join paths. Verify before starting:

```bash
ls src/cube/model/cubes/staff/
# must include: staff.yml  staff_work_history.yml  staff_reporting_relationships.yml
```

**dbt source models confirmed present:**

| Cube                        | dbt table                                 | Location            |
| --------------------------- | ----------------------------------------- | ------------------- |
| `staff_attrition`           | `fct_staff_attrition`                     | `marts/facts/`      |
| `staff_compensation`        | `fct_work_assignment_compensation`        | `marts/facts/`      |
| `staff_benefits`            | `fct_staff_benefits_enrollments`          | `marts/facts/`      |
| `staff_additional_earnings` | `fct_work_assignment_additional_earnings` | `marts/facts/`      |
| `staff_staffing_positions`  | `dim_staffing_positions`                  | `marts/dimensions/` |

**Tech Stack:** Cube YAML (`src/cube/model/`), Python parse verification
(`uv run python`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Task 1: Schema validation test (staff HR)

Extends the existing `tests/cube/test_cube_schema.py` with a staff HR-specific
test that asserts every new cube file in `cubes/staff/` (a) has `public: false`
at the cube level and (b) has every dimension/measure marked `public: true` that
appears in an `includes:` list in any view. The first assertion runs immediately
(new cubes are being written with `public: false`); the second asserts no
hidden-member errors will surface at query time.

**Files:**

- Modify: `tests/cube/test_cube_schema.py`

- [ ] **Step 1: Add the cube-level `public: false` test**

Append to `tests/cube/test_cube_schema.py`:

```python
@pytest.mark.parametrize(
    "yaml_file",
    list((CUBE_MODEL_DIR / "cubes" / "staff").rglob("*.yml")),
    ids=lambda p: str(p.relative_to(CUBE_MODEL_DIR)),
)
def test_staff_cube_public_false(yaml_file: Path) -> None:
    """All staff cubes must declare public: false at the cube level.

    The staff_ naming prefix drives queryRewrite's isStaffMember gate, but
    the cube still needs public: false so Cube doesn't expose it directly.
    See docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md#member-visibility.
    """
    data = yaml.safe_load(yaml_file.read_text())
    for cube in data.get("cubes", []):
        name = cube["name"]
        assert cube.get("public") is False, (
            f"{yaml_file.name}: cube '{name}' must set public: false"
        )
```

- [ ] **Step 2: Run to confirm test infrastructure is healthy**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: existing tests PASS; new parametrized test collects zero items (no
staff HR cube files yet) and shows as "no tests ran" for that case — not a
failure.

- [ ] **Step 3: Commit**

```bash
git add tests/cube/test_cube_schema.py
git commit -m "test(cube): add public:false assertion for staff HR cubes"
```

---

## Task 2: `staff_attrition` cube

Maps to `fct_staff_attrition`. Grain: one row per
`(employee_number, academic_year, attrition_type)`. FKs: `staff_key` → `staff`
cube; `staff_status_key` → `dim_staff_status` (no Cube cube for
`dim_staff_status` exists yet — join is omitted for now; the status fields
needed for consumer queries are `termination_reason` and
`termination_effective_date`, both degenerate on the fact). Date FK: no single
`date_key` column — the fact carries `cutoff_date` (a DATE), which role-plays to
`dim_dates` for time-dimension filtering.

**No `dim_dates` join is declared** because the fact has no single canonical
date FK — `cutoff_date` varies by attrition type (4/30 / 6/30 / 8/31 or the
actual termination date). Instead, `cutoff_date` is exposed directly as a
`type: time` dimension so views can filter by it.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_attrition.yml`

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: staff_attrition
    public: false
    sql_table: kipptaf_marts.fct_staff_attrition

    joins:
      - name: staff
        sql: "{staff.staff_key} = {CUBE}.staff_key"
        relationship: many_to_one

    dimensions:
      - name: staff_attrition_key
        sql: staff_attrition_key
        type: string
        primary_key: true

      - name: staff_key
        sql: staff_key
        type: string
        public: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: attrition_type
        sql: "`type`"
        type: string
        public: true

      - name: cutoff_date
        sql: CAST(cutoff_date AS TIMESTAMP)
        type: time
        public: true

      - name: is_attrition
        sql: is_attrition
        type: boolean
        public: true

      - name: termination_reason
        sql: termination_reason
        type: string
        public: true
        meta:
          pii: true

      - name: termination_effective_date
        sql: CAST(termination_effective_date AS TIMESTAMP)
        type: time
        public: true
        meta:
          pii: true

    measures:
      - name: count_staff
        description: Distinct staff members in the attrition cohort
        sql: staff_key
        type: count_distinct
        public: true

      - name: count_attrited
        description: Distinct staff members who attrited (is_attrition = true)
        sql: staff_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_attrition = true"

      - name: _count_total
        sql: staff_key
        type: count_distinct
        public: false

      - name: pct_attrition
        description: >
          Attrition rate — count_attrited / count_staff. Filter to a single
          attrition_type before comparing across years; mixing types
          double-counts staff.
        sql: "{count_attrited} / NULLIF({_count_total}, 0)"
        type: number
        format: percent
        public: true
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_attrition.yml').read_text())
cube = data['cubes'][0]
print('name:', cube['name'])
print('public:', cube['public'])
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
name: staff_attrition
public: False
dimensions: ['staff_attrition_key', 'staff_key', 'academic_year', 'attrition_type', 'cutoff_date', 'is_attrition', 'termination_reason', 'termination_effective_date']
measures: ['count_staff', 'count_attrited', '_count_total', 'pct_attrition']
```

- [ ] **Step 3: Run schema tests**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all tests PASS including the new `test_staff_cube_public_false`
parametrized case for `staff_attrition.yml`.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_attrition.yml
git commit -m "feat(cube): add staff_attrition cube (fct_staff_attrition)"
```

---

## Task 3: `staff_attrition` views

Two views: detail (individual staff records with PII gating) and summary
(aggregate breakdown with no direct identifiers). Both gate on
`staff_work_history.staff` for staff dimensions — the `staff_attrition` cube's
direct `staff` join provides the same path. Use `staff_attrition.staff` as the
join path prefix.

**Access policy:** Pattern 1 (PII) applies. `termination_reason` and
`termination_effective_date` are excluded by default under `detail-access`;
unlocked by `cube-access-staff-pii`. Summary view exposes no individual
identifiers.

**Files:**

- Create: `src/cube/model/views/staff/staff_attrition_detail.yml`
- Create: `src/cube/model/views/staff/staff_attrition_summary.yml`

- [ ] **Step 1: Write the detail view**

```yaml
views:
  - name: staff_attrition_detail
    description: >-
      Row-level staff attrition. One row per staff member x academic year x
      attrition methodology (foundation, nj_compliance, recruitment). Filter to
      a single attrition_type before computing pct_attrition — mixing types
      double-counts staff in the cohort. is_attrition = true identifies staff
      who did not return by the methodology's return-check date. Coverage begins
      with ADP era (2021+); pre-Dayforce staff are excluded.

      PII fields (termination_reason, termination_effective_date) require
      cube-access-staff-pii. Staff name and contact fields (staff_full_name,
      etc.) also require cube-access-staff-pii.

    cubes:
      - join_path: staff_attrition
        includes:
          - count_staff
          - count_attrited
          - pct_attrition
          - staff_key
          - academic_year
          - attrition_type
          - cutoff_date
          - is_attrition
          - termination_reason
          - termination_effective_date

      - join_path: staff_attrition.staff
        prefix: true
        includes:
          - full_name
          - first_name
          - last_name
          - work_email
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Attrition
          members:
            - academic_year
            - attrition_type
            - cutoff_date
            - is_attrition
            - termination_reason
            - termination_effective_date
        - name: Staff
          members:
            - staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - termination_reason
            - termination_effective_date
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            # google_email, personal_email, personal_cell_phone,
            # active_directory_username, staff_unique_id are not in this view's
            # staff includes — no excludes needed for fields not exposed.
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Write the summary view**

```yaml
views:
  - name: staff_attrition_summary
    description: >-
      Aggregated staff attrition. No direct staff identifiers. Filter to a
      single attrition_type before computing pct_attrition — mixing types
      double-counts staff in the cohort. Demographic breakdowns
      (gender_identity, race, is_hispanic) are aggregate-safe group-by
      dimensions. Coverage begins with ADP era (2021+).

    cubes:
      - join_path: staff_attrition
        includes:
          - count_staff
          - count_attrited
          - pct_attrition
          - academic_year
          - attrition_type
          - is_attrition

      - join_path: staff_attrition.staff
        prefix: true
        includes:
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Attrition
          members:
            - academic_year
            - attrition_type
            - is_attrition
        - name: Staff Demographics
          members:
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic

    access_policy:
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify both YAML files parse**

```bash
uv run python -c "
import yaml
from pathlib import Path

for name in ['staff_attrition_detail', 'staff_attrition_summary']:
    data = yaml.safe_load(Path(f'src/cube/model/views/staff/{name}.yml').read_text())
    view = data['views'][0]
    groups = [p['group'] for p in view['access_policy']]
    print(f'{name}: access groups = {groups}')
"
```

Expected output:

```text
staff_attrition_detail: access groups = ['detail-access', 'cube-access-staff-pii']
staff_attrition_summary: access groups = ['summary-access']
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/staff_attrition_detail.yml \
        src/cube/model/views/staff/staff_attrition_summary.yml
git commit -m "feat(cube): add staff_attrition detail and summary views"
```

---

## ~~Task 4: `staff_compensation` cube~~ — moved to staff-core plan

> **Architectural change:** `fct_work_assignment_compensation` has one row per
> work assignment per compensation period (no `earning_item_id` in PK), making
> it safe to add to `staff_work_history`'s GREATEST/LEAST period intersection as
> another SCD2 LEFT JOIN child. Compensation fields (`annual_wage`,
> `hourly_wage`, `daily_rate`, `period_rate`) are now dimensions on
> `staff_work_history` itself, exposed through the existing `staff_detail` and
> `staff_summary` views with `cube-access-staff-compensation` gating.
>
> **No `staff_compensation.yml` cube file is created.** All compensation work is
> in `2026-06-01-cube-staff-core-implementation.md` Task 3.

---

## ~~Task 5: `staff_compensation` views~~ — superseded

> Compensation fields are exposed through the core `staff_detail` /
> `staff_summary` views. No standalone `staff_compensation_detail.yml` or
> `staff_compensation_summary.yml` is created.

---

## Task 6 (renumbered from original Task 6): `staff_benefits` cube

Maps to `fct_staff_benefits_enrollments`. Grain: one row per
`(employee_number, plan_type, plan_name, enrollment_start_date)`. FK:
`staff_key` → `staff` cube. Date FKs: `start_date` and `end_date` are DATE
columns that role-play to `dim_dates`. The enrollment spans a date range (no
`date_key` equality join) — join `dates` via BETWEEN on `start_date` /
`end_date` with `relationship: one_to_many`.

**Benefits fields** (`plan_type`, `plan_name`, `coverage_level`) are gated by
Pattern 4 (`cube-access-staff-benefits`). All carry `meta: {pii: true}`. These
fields are the primary analytical content of this cube — without
`cube-access-staff-benefits`, the detail view exposes only `staff_key`, date
range, and counts.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_benefits.yml`

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: staff_benefits
    public: false
    sql_table: kipptaf_marts.fct_staff_benefits_enrollments

    joins:
      - name: dates
        sql: >
          {dates.date_day} BETWEEN CAST({CUBE}.start_date AS TIMESTAMP) AND
          CAST({CUBE}.end_date AS TIMESTAMP)
        relationship: one_to_many

      - name: staff
        sql: "{staff.staff_key} = {CUBE}.staff_key"
        relationship: many_to_one

    dimensions:
      - name: staff_benefits_enrollment_key
        sql: staff_benefits_enrollment_key
        type: string
        primary_key: true

      - name: staff_key
        sql: staff_key
        type: string
        public: true

      - name: plan_type
        sql: plan_type
        type: string
        public: true
        meta:
          pii: true

      - name: plan_name
        sql: plan_name
        type: string
        public: true
        meta:
          pii: true

      - name: coverage_level
        sql: coverage_level
        type: string
        public: true
        meta:
          pii: true

      - name: enrollment_start_date
        sql: CAST(start_date AS TIMESTAMP)
        type: time
        public: true

      - name: enrollment_end_date
        sql: CAST(end_date AS TIMESTAMP)
        type: time
        public: true

    measures:
      - name: count_enrolled
        description: Distinct staff members with a benefits enrollment record
        sql: staff_key
        type: count_distinct
        public: true

      - name: count_enrollments
        description:
          Total benefits enrollment records (one per plan per enrollment period)
        sql: staff_benefits_enrollment_key
        type: count
        public: true
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_benefits.yml').read_text())
cube = data['cubes'][0]
print('name:', cube['name'])
print('public:', cube['public'])
print('joins:', [j['name'] for j in cube['joins']])
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
name: staff_benefits
public: False
joins: ['dates', 'staff']
dimensions: ['staff_benefits_enrollment_key', 'staff_key', 'plan_type', 'plan_name', 'coverage_level', 'enrollment_start_date', 'enrollment_end_date']
measures: ['count_enrolled', 'count_enrollments']
```

- [ ] **Step 3: Run schema tests**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_benefits.yml
git commit -m "feat(cube): add staff_benefits cube (fct_staff_benefits_enrollments)"
```

---

## Task 7: `staff_benefits` views

Pattern 4 applies — `plan_type`, `plan_name`, `coverage_level` excluded by
default, unlocked by `cube-access-staff-benefits`. Detail view also applies
Pattern 1 for staff PII fields. Summary view exposes only counts (no plan
details) unless the user has `cube-access-staff-benefits`.

**Note:** Benefits data can reveal health information. Per ADA, it is treated
separately from general personnel records. The default detail-access view shows
only that an enrollment exists (count and dates) — not which plan. The
`cube-access-staff-benefits` block unlocks plan details.

**Files:**

- Create: `src/cube/model/views/staff/staff_benefits_detail.yml`
- Create: `src/cube/model/views/staff/staff_benefits_summary.yml`

- [ ] **Step 1: Write the detail view**

```yaml
views:
  - name: staff_benefits_detail
    description: >-
      Row-level staff benefits enrollments. One row per staff member x benefit
      plan x enrollment period. Without a date filter, each enrollment spans its
      full date range. Filter to a single date (enrollment_start_date or
      dates_date_day) for a point-in-time snapshot of active enrollments.

      Benefits plan fields (plan_type, plan_name, coverage_level) require
      cube-access-staff-benefits — these can reveal health information and are
      treated as ADA-protected. Staff name and contact fields require
      cube-access-staff-pii.

    cubes:
      - join_path: staff_benefits
        includes:
          - count_enrolled
          - count_enrollments
          - staff_key
          - plan_type
          - plan_name
          - coverage_level
          - enrollment_start_date
          - enrollment_end_date

      - join_path: staff_benefits.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_benefits.staff
        prefix: true
        includes:
          - full_name
          - first_name
          - last_name
          - work_email
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Benefits
          members:
            - enrollment_start_date
            - enrollment_end_date
            - plan_type
            - plan_name
            - coverage_level
        - name: Staff
          members:
            - staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - plan_type
            - plan_name
            - coverage_level
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            # google_email, personal_email, personal_cell_phone,
            # active_directory_username, staff_unique_id are not in this view's
            # staff includes — no excludes needed for fields not exposed.
      - group: cube-access-staff-benefits
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            # google_email, personal_email, personal_cell_phone,
            # active_directory_username, staff_unique_id are not in this view's
            # staff includes — no excludes needed for fields not exposed.
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Write the summary view**

```yaml
views:
  - name: staff_benefits_summary
    description: >-
      Aggregated staff benefits. No direct staff identifiers. count_enrolled
      reflects distinct staff with any active enrollment; count_enrollments
      counts individual plan-enrollment records. Plan details (plan_type,
      plan_name, coverage_level) require cube-access-staff-benefits.

    cubes:
      - join_path: staff_benefits
        includes:
          - count_enrolled
          - count_enrollments
          - plan_type
          - plan_name
          - coverage_level
          - enrollment_start_date

      - join_path: staff_benefits.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_benefits.staff
        prefix: true
        includes:
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Benefits
          members:
            - enrollment_start_date
            - plan_type
            - plan_name
            - coverage_level
        - name: Staff Demographics
          members:
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name

    access_policy:
      - group: summary-access
        member_level:
          includes: "*"
          excludes:
            - plan_type
            - plan_name
            - coverage_level
      - group: cube-access-staff-benefits
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify both YAML files parse**

```bash
uv run python -c "
import yaml
from pathlib import Path

for name in ['staff_benefits_detail', 'staff_benefits_summary']:
    data = yaml.safe_load(Path(f'src/cube/model/views/staff/{name}.yml').read_text())
    view = data['views'][0]
    groups = [p['group'] for p in view['access_policy']]
    paths = [c['join_path'] for c in view['cubes']]
    print(f'{name}:')
    print(f'  access groups = {groups}')
    print(f'  join paths = {paths}')
"
```

Expected output:

```text
staff_benefits_detail:
  access groups = ['detail-access', 'cube-access-staff-benefits', 'cube-access-staff-pii']
  join paths = ['staff_benefits', 'staff_benefits.dates', 'staff_benefits.staff']
staff_benefits_summary:
  access groups = ['summary-access', 'cube-access-staff-benefits']
  join paths = ['staff_benefits', 'staff_benefits.dates', 'staff_benefits.staff']
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/staff_benefits_detail.yml \
        src/cube/model/views/staff/staff_benefits_summary.yml
git commit -m "feat(cube): add staff_benefits detail and summary views"
```

---

## Task 8: `staff_additional_earnings` cube

Maps to `fct_work_assignment_additional_earnings`. Grain: one row per
`(work_assignment_key, earning_item_id, effective_start_date_key)` — a Type 2
SCD on additional remuneration lines. FKs: `work_assignment_key` →
`dim_staff_work_assignments` (joined via `staff_work_history` in views);
`effective_start_date_key` / `effective_end_date_key` → `dim_dates`
(role-playing dates, BETWEEN join, `relationship: one_to_many`).

**Compensation fields** (`rate_amount`, `earning_code`, `earning_description`)
are gated by Pattern 2 (`cube-access-staff-compensation`). All carry
`meta: {pii: true}`.

**Note:** `earning_code` and `earning_description` identify the type of
additional payment (e.g., "Rate 2"). These are compensation-adjacent and are
gated alongside `rate_amount` under `cube-access-staff-compensation`.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_additional_earnings.yml`

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: staff_additional_earnings
    public: false
    sql_table: kipptaf_marts.fct_work_assignment_additional_earnings

    joins:
      - name: dates
        sql: >
          {dates.date_day} BETWEEN CAST({CUBE}.effective_start_date_key AS
          TIMESTAMP) AND CAST({CUBE}.effective_end_date_key AS TIMESTAMP)
        relationship: one_to_many

      # Point-in-time lookup: each earnings row (keyed by work_assignment_key +
      # earning_item_id + effective_start_date_key) resolves to exactly one
      # staff_work_history period. Multiple earnings on the same date (e.g.
      # bonus + stipend) each independently hit the same work_history period —
      # no fan-out. many_to_one is correct.
      - name: staff_work_history
        sql: >
          {staff_work_history.work_assignment_key} = {CUBE}.work_assignment_key
          AND CAST({CUBE}.effective_start_date_key AS TIMESTAMP)
            BETWEEN {staff_work_history.effective_start_date}
            AND {staff_work_history.effective_end_date}
        relationship: many_to_one

    dimensions:
      - name: work_assignment_additional_earnings_key
        sql: work_assignment_additional_earnings_key
        type: string
        primary_key: true

      - name: work_assignment_key
        sql: work_assignment_key
        type: string
        public: true

      - name: effective_start_date
        sql: CAST(effective_start_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: effective_end_date
        sql: CAST(effective_end_date_key AS TIMESTAMP)
        type: time
        public: true

      - name: is_current
        sql: is_current
        type: boolean
        public: true

      - name: earning_code
        sql: earning_code
        type: string
        public: true
        meta:
          pii: true

      - name: earning_description
        sql: earning_description
        type: string
        public: true
        meta:
          pii: true

      - name: rate_amount
        sql: rate_amount
        type: number
        public: true
        meta:
          pii: true

    measures:
      - name: count_earning_lines
        description: Total additional earnings records in scope
        sql: work_assignment_additional_earnings_key
        type: count
        public: true

      - name: count_assignments
        description: Distinct work assignments with an additional earning record
        sql: work_assignment_key
        type: count_distinct
        public: true

      - name: sum_rate_amount
        description: Total additional earnings paid in scope
        sql: rate_amount
        type: sum
        public: true

      - name: avg_rate_amount
        description: Average additional earning amount per record in scope
        sql: rate_amount
        type: avg
        public: true
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_additional_earnings.yml').read_text())
cube = data['cubes'][0]
print('name:', cube['name'])
print('public:', cube['public'])
print('joins:', [j['name'] for j in cube['joins']])
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
name: staff_additional_earnings
public: False
joins: ['dates', 'staff_work_history']
dimensions: ['work_assignment_additional_earnings_key', 'work_assignment_key', 'effective_start_date', 'effective_end_date', 'is_current', 'earning_code', 'earning_description', 'rate_amount']
measures: ['count_earning_lines', 'count_assignments', 'sum_rate_amount', 'avg_rate_amount']
```

- [ ] **Step 3: Run schema tests**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_additional_earnings.yml
git commit -m "feat(cube): add staff_additional_earnings cube (fct_work_assignment_additional_earnings)"
```

---

## Task 9: `staff_additional_earnings` views

Pattern 2 applies — `rate_amount`, `earning_code`, `earning_description`
excluded by default, unlocked by `cube-access-staff-compensation`. Detail view
applies Pattern 1 for staff PII. Summary view exposes only counts unless the
user has `cube-access-staff-compensation`.

**Files:**

- Create: `src/cube/model/views/staff/staff_additional_earnings_detail.yml`
- Create: `src/cube/model/views/staff/staff_additional_earnings_summary.yml`

- [ ] **Step 1: Write the detail view**

```yaml
views:
  - name: staff_additional_earnings_detail
    description: >-
      Row-level additional earnings by work assignment. One row per work
      assignment x earning type x version (Type 2 SCD). Filter is_current = true
      for current earnings rates; filter to a single date for point-in-time.
      Without a date filter, each version fans out to one row per calendar day
      in its effective range.

      Earning fields (rate_amount, earning_code, earning_description) require
      cube-access-staff-compensation. Staff name and contact fields require
      cube-access-staff-pii.

    cubes:
      - join_path: staff_additional_earnings
        includes:
          - count_earning_lines
          - count_assignments
          - avg_rate_amount
          - work_assignment_key
          - effective_start_date
          - effective_end_date
          - is_current
          - earning_code
          - earning_description
          - rate_amount

      - join_path: staff_additional_earnings.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_additional_earnings.staff_work_history
        prefix: true
        includes:
          - status_name
          - position_title
          - worker_type
          - department_name
          - business_unit_name
          - is_primary_position

      - join_path: staff_additional_earnings.staff_work_history.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Earnings
          members:
            - effective_start_date
            - effective_end_date
            - is_current
            - earning_code
            - earning_description
            - rate_amount
        - name: Assignment
          members:
            - work_assignment_key
            - staff_work_history_status_name
            - staff_work_history_position_title
            - staff_work_history_worker_type
            - staff_work_history_department_name
            - staff_work_history_business_unit_name
            - staff_work_history_is_primary_position
        - name: Staff
          members:
            - staff_staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - rate_amount
            - earning_code
            - earning_description
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            # google_email, personal_email, personal_cell_phone,
            # active_directory_username, staff_unique_id are not in this view's
            # staff includes — no excludes needed for fields not exposed.
      - group: cube-access-staff-compensation
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            # google_email, personal_email, personal_cell_phone,
            # active_directory_username, staff_unique_id are not in this view's
            # staff includes — no excludes needed for fields not exposed.
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Write the summary view**

```yaml
views:
  - name: staff_additional_earnings_summary
    description: >-
      Aggregated additional earnings. No direct staff identifiers.
      avg_rate_amount, earning_code, and earning_description require
      cube-access-staff-compensation. count_earning_lines and count_assignments
      are available without compensation access.

    cubes:
      - join_path: staff_additional_earnings
        includes:
          - count_earning_lines
          - count_assignments
          - avg_rate_amount
          - is_current
          - effective_start_date
          - earning_code
          - earning_description

      - join_path: staff_additional_earnings.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_additional_earnings.staff_work_history
        prefix: true
        includes:
          - status_name
          - position_title
          - worker_type
          - department_name
          - business_unit_name

      - join_path: staff_additional_earnings.staff_work_history.staff
        prefix: true
        includes:
          - gender_identity
          - race
          - is_hispanic

    meta:
      folders:
        - name: Earnings
          members:
            - effective_start_date
            - is_current
            - earning_code
            - earning_description
        - name: Assignment
          members:
            - staff_work_history_status_name
            - staff_work_history_position_title
            - staff_work_history_worker_type
            - staff_work_history_department_name
            - staff_work_history_business_unit_name
        - name: Staff Demographics
          members:
            - staff_gender_identity
            - staff_race
            - staff_is_hispanic
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name

    access_policy:
      - group: summary-access
        member_level:
          includes: "*"
          excludes:
            - avg_rate_amount
            - earning_code
            - earning_description
      - group: cube-access-staff-compensation
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify both YAML files parse**

```bash
uv run python -c "
import yaml
from pathlib import Path

for name in ['staff_additional_earnings_detail', 'staff_additional_earnings_summary']:
    data = yaml.safe_load(Path(f'src/cube/model/views/staff/{name}.yml').read_text())
    view = data['views'][0]
    groups = [p['group'] for p in view['access_policy']]
    paths = [c['join_path'] for c in view['cubes']]
    print(f'{name}:')
    print(f'  access groups = {groups}')
    print(f'  join paths = {paths}')
"
```

Expected output:

```text
staff_additional_earnings_detail:
  access groups = ['detail-access', 'cube-access-staff-compensation', 'cube-access-staff-pii']
  join paths = ['staff_additional_earnings', 'staff_additional_earnings.dates', 'staff_additional_earnings.staff_work_history', 'staff_additional_earnings.staff_work_history.staff']
staff_additional_earnings_summary:
  access groups = ['summary-access', 'cube-access-staff-compensation']
  join paths = ['staff_additional_earnings', 'staff_additional_earnings.dates', 'staff_additional_earnings.staff_work_history', 'staff_additional_earnings.staff_work_history.staff']
```

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/staff_additional_earnings_detail.yml \
        src/cube/model/views/staff/staff_additional_earnings_summary.yml
git commit -m "feat(cube): add staff_additional_earnings detail and summary views"
```

---

## Task 10: `staff_staffing_positions` cube

Maps to `dim_staffing_positions`. Grain: one row per staffing position version
(dbt snapshot SCD2). FKs: `location_key` → `locations` cube;
`incumbent_staff_key` → `staff` cube (role-playing incumbent);
`recruiter_staff_key` → no dedicated role alias cube planned in this spec —
leave recruiter FK as a degenerate key dimension for now. No shared key to
`dim_staff_work_assignments` (per spec: "SmartRecruiters and ADP/Seat Tracker
have no shared key"). This cube is standalone.

**SCD2 note:** `effective_start_date` / `effective_end_date` span the position
version. Join `dates` via BETWEEN with `relationship: one_to_many`. BI consumers
must apply a date or `academic_year` filter; without one, each position version
fans out one row per day.

**No compensation, benefits, or PII data** — this cube contains position
planning metadata only. No special access group is required beyond the standard
`staff_` gate and the `detail-access` / `summary-access` split.

**`title` is a BigQuery reserved word** — backtick in SQL, `public: true` on the
dimension.

**Files:**

- Create: `src/cube/model/cubes/staff/staff_staffing_positions.yml`

- [ ] **Step 1: Write the cube file**

```yaml
cubes:
  - name: staff_staffing_positions
    public: false
    sql_table: kipptaf_marts.dim_staffing_positions

    joins:
      - name: dates
        sql: >
          {dates.date_day} BETWEEN CAST({CUBE}.effective_start_date AS
          TIMESTAMP) AND COALESCE(CAST({CUBE}.effective_end_date AS TIMESTAMP),
                   CAST('9999-12-31' AS TIMESTAMP))
        relationship: one_to_many

      - name: locations
        sql: "{locations.location_key} = {CUBE}.location_key"
        relationship: many_to_one

      - name: staff
        # incumbent staff member filling the position; nullable for open positions
        sql: "{staff.staff_key} = {CUBE}.incumbent_staff_key"
        relationship: many_to_one

    dimensions:
      - name: staffing_position_key
        sql: staffing_position_key
        type: string
        primary_key: true

      - name: location_key
        sql: location_key
        type: string
        public: true

      - name: incumbent_staff_key
        sql: incumbent_staff_key
        type: string
        public: true

      - name: recruiter_staff_key
        sql: recruiter_staff_key
        type: string
        public: true

      - name: academic_year
        sql: academic_year
        type: number
        public: true

      - name: recruitment_group
        sql: recruitment_group
        type: string
        public: true

      - name: home_department_name
        sql: home_department_name
        type: string
        public: true

      - name: position_title
        sql: "`title`"
        type: string
        public: true

      - name: is_active
        sql: is_active
        type: boolean
        public: true

      - name: status
        sql: "`status`"
        type: string
        public: true

      - name: status_detail
        sql: status_detail
        type: string
        public: true

      - name: is_mid_year_hire
        sql: is_mid_year_hire
        type: boolean
        public: true

      - name: effective_start_date
        sql: CAST(effective_start_date AS TIMESTAMP)
        type: time
        public: true

      - name: effective_end_date
        sql: CAST(effective_end_date AS TIMESTAMP)
        type: time
        public: true

    measures:
      - name: count_positions
        description: Total staffing position versions in scope
        sql: staffing_position_key
        type: count
        public: true

      - name: count_open_positions
        description: >
          Distinct open position versions (status = 'Open' and is_active =
          true). Filter to a point in time for current open headcount.
        sql: staffing_position_key
        type: count
        public: true
        filters:
          - sql: "{CUBE}.`status` = 'Open' AND {CUBE}.is_active = true"

      - name: count_staffed_positions
        description: >
          Distinct staffed position versions (status = 'Staffed' and is_active =
          true). Filter to a point in time for current staffed headcount.
        sql: staffing_position_key
        type: count
        public: true
        filters:
          - sql: "{CUBE}.`status` = 'Staffed' AND {CUBE}.is_active = true"
```

- [ ] **Step 2: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
data = yaml.safe_load(Path('src/cube/model/cubes/staff/staff_staffing_positions.yml').read_text())
cube = data['cubes'][0]
print('name:', cube['name'])
print('public:', cube['public'])
print('joins:', [j['name'] for j in cube['joins']])
print('dimensions:', [d['name'] for d in cube['dimensions']])
print('measures:', [m['name'] for m in cube['measures']])
"
```

Expected output:

```text
name: staff_staffing_positions
public: False
joins: ['dates', 'locations', 'staff']
dimensions: ['staffing_position_key', 'location_key', 'incumbent_staff_key', 'recruiter_staff_key', 'academic_year', 'recruitment_group', 'home_department_name', 'position_title', 'is_active', 'status', 'status_detail', 'is_mid_year_hire', 'effective_start_date', 'effective_end_date']
measures: ['count_positions', 'count_open_positions', 'count_staffed_positions']
```

- [ ] **Step 3: Run schema tests**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff_staffing_positions.yml
git commit -m "feat(cube): add staff_staffing_positions cube (dim_staffing_positions)"
```

---

## Task 11: `staff_staffing_positions` views

No compensation or benefits gating needed. Detail view applies Pattern 1 for the
incumbent staff PII fields reached via the `staff` join path. Summary view
exposes only position planning dimensions and aggregate counts — no individual
incumbent identifiers.

**`effective_end_date` is nullable** — open-ended current versions have NULL.
The COALESCE in the `dates` join SQL handles this; in the view, expose both
dates so consumers can identify open-ended positions.

**Files:**

- Create: `src/cube/model/views/staff/staff_staffing_positions_detail.yml`
- Create: `src/cube/model/views/staff/staff_staffing_positions_summary.yml`

- [ ] **Step 1: Write the detail view**

```yaml
views:
  - name: staff_staffing_positions_detail
    description: >-
      Row-level staffing positions (budgeted seat tracker). One row per position
      version. effective_end_date is null for the current active version. Filter
      to a single academic_year or a point-in-time date to avoid fan-out —
      without a filter each version expands one row per day in its effective
      range.

      This view is standalone: dim_staffing_positions has no shared key to
      dim_staff_work_assignments (Seat Tracker and ADP have no common
      identifier). Headcount comparisons between staffing positions and work
      assignments require matching on location and position_title, not on a
      surrogate key.

      Incumbent staff name and contact fields require cube-access-staff-pii.

    cubes:
      - join_path: staff_staffing_positions
        includes:
          - count_positions
          - count_open_positions
          - count_staffed_positions
          - location_key
          - incumbent_staff_key
          - academic_year
          - recruitment_group
          - home_department_name
          - position_title
          - is_active
          - status
          - status_detail
          - is_mid_year_hire
          - effective_start_date
          - effective_end_date

      - join_path: staff_staffing_positions.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_staffing_positions.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - city

      - join_path: staff_staffing_positions.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: staff_staffing_positions.staff
        prefix: true
        includes:
          - staff_key
          - full_name
          - first_name
          - last_name
          - work_email

    meta:
      folders:
        - name: Position
          members:
            - academic_year
            - recruitment_group
            - home_department_name
            - position_title
            - is_active
            - status
            - status_detail
            - is_mid_year_hire
            - effective_start_date
            - effective_end_date
        - name: Incumbent
          members:
            - incumbent_staff_key
            - staff_staff_key
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
        - name: Location
          members:
            - location_key
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_city
            - regions_region_name
            - regions_state
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name

    access_policy:
      - group: detail-access
        member_level:
          includes: "*"
          excludes:
            - staff_full_name
            - staff_first_name
            - staff_last_name
            - staff_work_email
            # google_email, personal_email, personal_cell_phone,
            # active_directory_username, staff_unique_id are not in this view's
            # staff includes — no excludes needed for fields not exposed.
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Write the summary view**

```yaml
views:
  - name: staff_staffing_positions_summary
    description: >-
      Aggregated staffing positions for open-seat and recruitment planning. No
      individual identifiers. count_open_positions and count_staffed_positions
      are the primary KPIs; filter to a single academic_year or point-in-time
      date. Without a date filter, each position version fans out per day.

    cubes:
      - join_path: staff_staffing_positions
        includes:
          - count_positions
          - count_open_positions
          - count_staffed_positions
          - academic_year
          - recruitment_group
          - home_department_name
          - position_title
          - is_active
          - status
          - status_detail
          - is_mid_year_hire
          - effective_start_date

      - join_path: staff_staffing_positions.dates
        prefix: true
        includes:
          - date_day
          - academic_year
          - month_name

      - join_path: staff_staffing_positions.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - city

      - join_path: staff_staffing_positions.locations.regions
        prefix: true
        includes:
          - region_name
          - state

    meta:
      folders:
        - name: Position
          members:
            - academic_year
            - recruitment_group
            - home_department_name
            - position_title
            - is_active
            - status
            - status_detail
            - is_mid_year_hire
            - effective_start_date
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_city
            - regions_region_name
            - regions_state
        - name: Date
          members:
            - dates_date_day
            - dates_academic_year
            - dates_month_name

    access_policy:
      - group: summary-access
        member_level:
          includes: "*"
```

- [ ] **Step 3: Verify both YAML files parse**

```bash
uv run python -c "
import yaml
from pathlib import Path

for name in ['staff_staffing_positions_detail', 'staff_staffing_positions_summary']:
    data = yaml.safe_load(Path(f'src/cube/model/views/staff/{name}.yml').read_text())
    view = data['views'][0]
    groups = [p['group'] for p in view['access_policy']]
    paths = [c['join_path'] for c in view['cubes']]
    print(f'{name}:')
    print(f'  access groups = {groups}')
    print(f'  join paths = {paths}')
"
```

Expected output:

```text
staff_staffing_positions_detail:
  access groups = ['detail-access', 'cube-access-staff-pii']
  join paths = ['staff_staffing_positions', 'staff_staffing_positions.dates', 'staff_staffing_positions.locations', 'staff_staffing_positions.locations.regions', 'staff_staffing_positions.staff']
staff_staffing_positions_summary:
  access groups = ['summary-access']
  join paths = ['staff_staffing_positions', 'staff_staffing_positions.dates', 'staff_staffing_positions.locations', 'staff_staffing_positions.locations.regions']
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/staff/staff_staffing_positions_detail.yml \
        src/cube/model/views/staff/staff_staffing_positions_summary.yml
git commit -m "feat(cube): add staff_staffing_positions detail and summary views"
```

---

## Validation in Cube Cloud

After all tasks are committed and pushed, validate in Cube Cloud Dev Mode. Add
the feature branch in Cube Cloud → Data Model → Dev Mode to spin up a per-branch
endpoint.

**Check 1 — Model loads (meta confirms all five views present):**

```bash
curl -s -X GET "<DEV_MODE_URL>/cubejs-api/v1/meta" \
  -H "Authorization: <JWT>" \
  | jq '[.cubes[].name] | sort'
```

Expected: the five new view names appear in the list: `staff_attrition_detail`,
`staff_attrition_summary`, `staff_compensation_detail`,
`staff_compensation_summary`, `staff_benefits_detail`, `staff_benefits_summary`,
`staff_additional_earnings_detail`, `staff_additional_earnings_summary`,
`staff_staffing_positions_detail`, `staff_staffing_positions_summary`.

**Check 2 — Compensation fields hidden from base access:**

```bash
# user with detail-access but NOT cube-access-staff-compensation
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-detail-no-comp>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["staff_compensation_detail.annual_wage"],"limit":1}}' \
  | jq '.error // "no error"'
```

Expected: an error containing "hidden member" or "You requested hidden member
annual_wage".

**Check 3 — Benefits fields hidden from base access:**

```bash
# user with detail-access but NOT cube-access-staff-benefits
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-detail-no-benefits>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["staff_benefits_detail.plan_type"],"limit":1}}' \
  | jq '.error // "no error"'
```

Expected: an error containing "hidden member".

**Check 4 — `isStaffMember` gate fires on staff HR cubes:**

All five cube names start with `staff_` — confirm `queryRewrite`'s
`isStaffMember` helper covers them without listing them explicitly. Query
`staff_attrition_summary.count_staff` as a user with no `cube-access-staff-*`
group but with a valid scope group — the SQL should contain `WHERE (1 = 0)` or
return zero rows if the reporting chain segment filters out all staff.

**Check 5 — `staff_staffing_positions` standalone confirmed:**

```bash
# attempt a join from staff_staffing_positions to staff_work_history — must fail or return no join path
curl -s -X POST "<DEV_MODE_URL>/cubejs-api/v1/sql" \
  -H "Authorization: <JWT-network-detail>" \
  -H "Content-Type: application/json" \
  -d '{"query":{"dimensions":["staff_staffing_positions_detail.position_title","staff_staffing_positions_detail.status"],"measures":["staff_staffing_positions_detail.count_open_positions"],"limit":5}}' \
  | jq '.sql'
```

Expected: a valid SQL string — the standalone query succeeds without needing a
work_assignments join.

---

## Blockers and deferral notes

| Item                                              | Status                     | Notes                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `staff_compensation` join to `staff_work_history` | Depends on Staff Core plan | `staff_work_history.yml` must exist in `cubes/staff/`; the join is `{staff_work_history.work_assignment_key} = {CUBE}.work_assignment_key`                                                                                                                                                                          |
| `staff_additional_earnings` same join             | Depends on Staff Core plan | Same dependency as above                                                                                                                                                                                                                                                                                            |
| `recruiter_staff_key` role alias                  | Deferred                   | A `staff_recruiter` cube extending `staff` (for role-playing FK pattern) is not in this plan — recruiter lookup is exposed as a degenerate key only. File a follow-up issue if recruiter attribution becomes a consumer requirement.                                                                                |
| `dim_staff_status` cube                           | Deferred                   | `fct_staff_attrition.staff_status_key` FKs to `dim_staff_status` but no Cube cube exists for it. `termination_reason` and `termination_effective_date` are degenerate on the fact and do not require a `dim_staff_status` join for the consumer use case. File a follow-up when status-timeline analysis is needed. |
