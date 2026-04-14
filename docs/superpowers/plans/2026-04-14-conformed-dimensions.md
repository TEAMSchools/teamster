# Conformed Dimensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 5 conformed dimensions that form the foundation for every
domain in the star schema data mart.

**Architecture:** Conformed dimensions live in `models/marts/dimensions/` with
enforced contracts. They are joinable from any fact or dimension in the mart.
Existing prototype models (`dim_dates`, `dim_terms`, `dim_locations`) are moved
into the new directory structure and revised to match the spec. Two new models
(`dim_regions`, `dim_school_calendars`) are created.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`uv run dbt build` for compilation + testing.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Conformed
Dimensions section.

**dbt conventions reference:** `src/dbt/CLAUDE.md` and
`src/dbt/kipptaf/CLAUDE.md`.

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All commands use `uv run` prefix (never bare `dbt`)
- All file paths are relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                  | Action           | Dependencies |
| ---- | ---------------------- | ---------------- | ------------ |
| 0    | (directory setup)      | create           | none         |
| 1    | `dim_dates`            | move + revise    | Task 0       |
| 2    | `dim_regions`          | create           | Task 0       |
| 3    | `dim_terms`            | move + revise    | Task 0       |
| 4    | `dim_locations`        | move + revise    | Task 0       |
| 5    | `dim_school_calendars` | create           | Tasks 1, 4   |
| 6    | cleanup                | delete old files | Tasks 1-5    |

---

### Task 0: Create directory structure

**Files:**

- Create: `models/marts/dimensions/` (directory)
- Create: `models/marts/dimensions/properties/` (directory)
- Create: `models/marts/facts/` (directory)
- Create: `models/marts/facts/properties/` (directory)
- Create: `models/marts/bridges/` (directory)
- Create: `models/marts/bridges/properties/` (directory)

- [ ] **Step 1: Create subdirectories**

```bash
mkdir -p src/dbt/kipptaf/models/marts/{dimensions,facts,bridges}/properties
```

- [ ] **Step 2: Add .gitkeep files to empty directories**

```bash
touch src/dbt/kipptaf/models/marts/facts/.gitkeep
touch src/dbt/kipptaf/models/marts/facts/properties/.gitkeep
touch src/dbt/kipptaf/models/marts/bridges/.gitkeep
touch src/dbt/kipptaf/models/marts/bridges/properties/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/ src/dbt/kipptaf/models/marts/facts/ src/dbt/kipptaf/models/marts/bridges/
git commit -m "chore: create marts subdirectory structure (dimensions, facts, bridges)"
```

---

### Task 1: `dim_dates`

Revise the existing generated date dimension. Changes from prototype: extend
range to 2000-01-01 through 9999-12-31, add a DATE primary key column
(`date_key`), add calendar attribute columns (day_of_week, month, quarter, year,
is_weekday), add `date_timestamp` column for Cube, add uniqueness test.

The spec says date keys are raw DATE types. Fact and dimension tables join to
`dim_dates` on the DATE key directly. `dim_dates` carries a `date_timestamp`
column (TIMESTAMP cast) for Cube, which requires timestamps for date dimension
joins.

**Files:**

- Create: `models/marts/dimensions/dim_dates.sql`
- Create: `models/marts/dimensions/properties/dim_dates.yml`

- [ ] **Step 1: Write YAML contract**

Create `src/dbt/kipptaf/models/marts/dimensions/properties/dim_dates.yml`:

```yaml
models:
  - name: dim_dates
    description: >-
      Generated calendar date dimension. One row per calendar date from
      2000-01-01 through 9999-12-31. Conformed dimension joinable from any fact
      or dimension in the mart via DATE key.
    config:
      materialized: table
    columns:
      - name: date_key
        data_type: date
        description: >-
          Calendar date. Primary key and join target for all mart models.
        data_tests:
          - unique
          - not_null

      - name: date_timestamp
        data_type: timestamp
        description: >-
          Timestamp cast of date_key. Required by Cube for date dimension joins.

      - name: day_of_week
        data_type: int64
        description: >-
          ISO day of week (1=Monday through 7=Sunday).

      - name: day_of_week_name
        data_type: string
        description: >-
          Full day name (Monday, Tuesday, etc.).

      - name: day_of_month
        data_type: int64
        description: >-
          Day of month (1-31).

      - name: day_of_year
        data_type: int64
        description: >-
          Day of year (1-366).

      - name: week_of_year
        data_type: int64
        description: >-
          ISO week number (1-53).

      - name: month_number
        data_type: int64
        description: >-
          Month number (1-12).

      - name: month_name
        data_type: string
        description: >-
          Full month name (January, February, etc.).

      - name: quarter_number
        data_type: int64
        description: >-
          Calendar quarter (1-4).

      - name: year_number
        data_type: int64
        description: >-
          Calendar year.

      - name: is_weekday
        data_type: boolean
        description: >-
          TRUE for Monday through Friday.

      - name: academic_year
        data_type: int64
        description: >-
          KIPP academic year (July start). The calendar year in which the
          academic year begins (e.g., 2025 for the 2025-26 school year).

      - name: fiscal_year
        data_type: int64
        description: >-
          KIPP fiscal year (July start). The calendar year in which the fiscal
          year ends (e.g., 2026 for FY2026 which begins July 2025).

      - name: week_start_date
        data_type: date
        description: >-
          Start of the ISO week (Sunday) containing this date.

      - name: week_end_date
        data_type: date
        description: >-
          End of the ISO week (Saturday) containing this date.

      - name: week_start_monday
        data_type: date
        description: >-
          Start of the Monday-based week containing this date.

      - name: week_end_sunday
        data_type: date
        description: >-
          End of the Monday-based week (Sunday) containing this date.
```

- [ ] **Step 2: Write SQL model**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_dates.sql`:

```sql
with
    date_spine as (
        select date_value,
        from
            unnest(
                generate_date_array(
                    date(2000, 1, 1),
                    date(9999, 12, 31),
                    interval 1 day
                )
            ) as date_value
    )

select
    date_value as date_key,

    cast(date_value as timestamp) as date_timestamp,

    extract(dayofweek from date_value) as day_of_week,
    format_date('%A', date_value) as day_of_week_name,
    extract(day from date_value) as day_of_month,
    extract(dayofyear from date_value) as day_of_year,
    extract(isoweek from date_value) as week_of_year,
    extract(month from date_value) as month_number,
    format_date('%B', date_value) as month_name,
    extract(quarter from date_value) as quarter_number,
    extract(year from date_value) as year_number,

    extract(dayofweek from date_value) between 2 and 6 as is_weekday,

    {{
        date_to_fiscal_year(
            date_field="date_value", start_month=7, year_source="start"
        )
    }} as academic_year,

    {{
        date_to_fiscal_year(
            date_field="date_value", start_month=7, year_source="end"
        )
    }} as fiscal_year,

    date_trunc(date_value, week) as week_start_date,
    last_day(date_value, week) as week_end_date,

    -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
    date_trunc(date_value, week(monday)) as week_start_monday,

    -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
    last_day(date_value, week(monday)) as week_end_sunday,
from date_spine
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build -s dim_dates --project-dir src/dbt/kipptaf
```

Expected: model builds as a table, uniqueness and not_null tests pass on
`date_key`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_dates.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_dates.yml
git commit -m "feat(marts): revise dim_dates with DATE key and calendar attributes"
```

---

### Task 2: `dim_regions`

New model. Simple reference dimension with one row per KIPP region. Hardcoded
from known regions — no upstream staging model needed.

**Files:**

- Create: `models/marts/dimensions/dim_regions.sql`
- Create: `models/marts/dimensions/properties/dim_regions.yml`

- [ ] **Step 1: Write YAML contract**

Create `src/dbt/kipptaf/models/marts/dimensions/properties/dim_regions.yml`:

```yaml
models:
  - name: dim_regions
    description: >-
      Region reference dimension. One row per KIPP region. Conformed dimension
      joinable from any fact or dimension that carries a region context.
    columns:
      - name: region_key
        data_type: string
        description: >-
          Surrogate key derived from region name.
        data_tests:
          - unique
          - not_null

      - name: region
        data_type: string
        description: >-
          Region name (Newark, Camden, Miami, Paterson).

      - name: state
        data_type: string
        description: >-
          US state (NJ or FL).

      - name: timezone
        data_type: string
        description: >-
          IANA timezone identifier.

      - name: legal_entity
        data_type: string
        description: >-
          Legal entity name for this region in ADP.
```

- [ ] **Step 2: Write SQL model**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_regions.sql`:

```sql
with
    regions as (
        select
            'Newark' as region,
            'NJ' as state,
            'America/New_York' as timezone,
            'TEAM Academy Charter School' as legal_entity,
        union all
        select
            'Camden' as region,
            'NJ' as state,
            'America/New_York' as timezone,
            'KIPP Cooper Norcross Academy' as legal_entity,
        union all
        select
            'Miami' as region,
            'FL' as state,
            'America/New_York' as timezone,
            'KIPP Miami' as legal_entity,
        union all
        select
            'Paterson' as region,
            'NJ' as state,
            'America/New_York' as timezone,
            'KIPP Paterson' as legal_entity,
    )

select
    {{ dbt_utils.generate_surrogate_key(["region"]) }} as region_key,

    region,
    state,
    timezone,
    legal_entity,
from regions
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build -s dim_regions --project-dir src/dbt/kipptaf
```

Expected: model builds as a view (default materialization), uniqueness and
not_null tests pass on `region_key`. Should produce exactly 4 rows.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_regions.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_regions.yml
git commit -m "feat(marts): add dim_regions conformed dimension"
```

---

### Task 3: `dim_terms`

Revise the existing terms dimension. Changes from prototype: rename columns to
generic convention (`entity` → `region`, `terms_key` → `term_key`), cast dates
to DATE type (spec says date keys are raw DATE types, but term start/end are not
join targets for dim_dates — they are descriptive attributes).

**Files:**

- Create: `models/marts/dimensions/dim_terms.sql`
- Create: `models/marts/dimensions/properties/dim_terms.yml`

**Upstream:** `stg_google_sheets__reporting__terms`

- [ ] **Step 1: Write YAML contract**

Create `src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml`:

```yaml
models:
  - name: dim_terms
    description: >-
      Generalized term/period dimension. One row per named period per region.
      Covers academic terms, performance management rounds, survey windows,
      assessment administration windows, and fiscal periods. Region is nullable
      for org-wide periods like fiscal quarters. Conformed dimension joinable
      from any fact or dimension that operates within a defined time period.
    columns:
      - name: term_key
        data_type: string
        description: >-
          Surrogate key derived from term type, code, name, start date, region,
          and school ID.
        data_tests:
          - unique
          - not_null

      - name: term_type
        data_type: string
        description: >-
          Category of period (e.g., academic, PM, survey, assessment, fiscal).

      - name: term_code
        data_type: string
        description: >-
          Short code for the period (e.g., Q1, Q2, PM1, Fall).

      - name: term_name
        data_type: string
        description: >-
          Display name for the period.

      - name: term_start_date
        data_type: date
        description: >-
          First day of the period.

      - name: term_end_date
        data_type: date
        description: >-
          Last day of the period.

      - name: academic_year
        data_type: int64
        description: >-
          Academic year this period falls within.

      - name: fiscal_year
        data_type: int64
        description: >-
          Fiscal year this period falls within.

      - name: region
        data_type: string
        description: >-
          Region this period applies to. Nullable for org-wide periods.

      - name: school_id
        data_type: int64
        description: >-
          PowerSchool school ID. Nullable when the period is region-wide.

      - name: grade_band
        data_type: string
        description: >-
          Grade band (ES, MS, HS). Nullable when not school-specific.

      - name: lockbox_date
        data_type: date
        description: >-
          Date after which grades are locked for this period.

      - name: is_current
        data_type: boolean
        description: >-
          TRUE if the current date falls within this period, or if the period is
          the latest for its type in a past academic year.

      - name: powerschool_year_id
        data_type: int64
        description: >-
          PowerSchool year_id for joining to PowerSchool term tables.

      - name: powerschool_term_id
        data_type: int64
        description: >-
          PowerSchool term_id for joining to PowerSchool term tables.
```

- [ ] **Step 2: Write SQL model**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql`:

```sql
select
    {{
        dbt_utils.generate_surrogate_key(
            ["type", "code", "name", "start_date", "region", "school_id"]
        )
    }} as term_key,

    `type` as term_type,
    code as term_code,
    `name` as term_name,
    `start_date` as term_start_date,
    end_date as term_end_date,
    academic_year,
    fiscal_year,
    region,
    school_id,
    grade_band,
    lockbox_date,
    is_current,
    powerschool_year_id,
    powerschool_term_id,
from {{ ref("stg_google_sheets__reporting__terms") }}
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build -s dim_terms --project-dir src/dbt/kipptaf
```

Expected: model builds as a view, uniqueness and not_null tests pass on
`term_key`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml
git commit -m "feat(marts): revise dim_terms with generic column naming"
```

---

### Task 4: `dim_locations`

Revise the existing locations dimension. Changes from prototype: drop
`location_` prefix from columns, add `region` column (for chain traversal to
`dim_regions`), keep campus grouping.

**Files:**

- Create: `models/marts/dimensions/dim_locations.sql`
- Create: `models/marts/dimensions/properties/dim_locations.yml`

**Upstream:** `int_people__location_crosswalk`

- [ ] **Step 1: Write YAML contract**

Create `src/dbt/kipptaf/models/marts/dimensions/properties/dim_locations.yml`:

```yaml
models:
  - name: dim_locations
    description: >-
      School and office location dimension. One row per school or office.
      Conformed dimension. Region context is reached by joining this model's
      region column to dim_regions. Campus is a physical site grouping where
      multiple schools share a building.
    columns:
      - name: location_key
        data_type: string
        description: >-
          Surrogate key derived from location name.
        data_tests:
          - unique
          - not_null

      - name: location_name
        data_type: string
        description: >-
          Canonical location name.

      - name: abbreviation
        data_type: string
        description: >-
          Short display name for the location.

      - name: region
        data_type: string
        description: >-
          Region this location belongs to (Newark, Camden, Miami, Paterson).

      - name: grade_band
        data_type: string
        description: >-
          Grade band served (ES, MS, HS).

      - name: campus
        data_type: string
        description: >-
          Physical campus name. Multiple schools may share a campus.

      - name: is_campus
        data_type: boolean
        description: >-
          TRUE if this location record represents a campus-level entity.

      - name: powerschool_school_id
        data_type: int64
        description: >-
          PowerSchool school_id for joining to PowerSchool tables.

      - name: deanslist_school_id
        data_type: int64
        description: >-
          DeansList school_id for joining to DeansList tables.
```

- [ ] **Step 2: Write SQL model**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_locations.sql`:

```sql
select distinct
    {{ dbt_utils.generate_surrogate_key(["location_clean_name"]) }}
    as location_key,

    location_clean_name as location_name,
    coalesce(location_abbreviation, location_clean_name) as abbreviation,
    location_region as region,
    location_grade_band as grade_band,
    campus_name as campus,
    location_is_campus as is_campus,
    location_powerschool_school_id as powerschool_school_id,
    location_deanslist_school_id as deanslist_school_id,
from {{ ref("int_people__location_crosswalk") }}
where not location_is_pathways and location_clean_name <> 'KIPP Whittier Elementary'
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build -s dim_locations --project-dir src/dbt/kipptaf
```

Expected: model builds as a view, uniqueness and not_null tests pass on
`location_key`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_locations.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_locations.yml
git commit -m "feat(marts): revise dim_locations with generic column naming"
```

---

### Task 5: `dim_school_calendars`

New model. One row per date per school. Indicates whether each date is an
in-session day and a membership day for that school. FK to `dim_dates` and
`dim_locations`.

**Files:**

- Create: `models/marts/dimensions/dim_school_calendars.sql`
- Create: `models/marts/dimensions/properties/dim_school_calendars.yml`

**Upstream:** `stg_powerschool__calendar_day` (kipptaf union model)

- [ ] **Step 1: Write YAML contract**

Create
`src/dbt/kipptaf/models/marts/dimensions/properties/dim_school_calendars.yml`:

```yaml
models:
  - name: dim_school_calendars
    description: >-
      School calendar dimension. One row per date per school. Indicates whether
      each date is an in-session day and a membership day. Conformed dimension
      used by attendance (session validity) and assessments (school-day counts
      for progress monitoring goals). FK to dim_dates and dim_locations.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - date_key
            - location_key

    columns:
      - name: date_key
        data_type: date
        description: >-
          Calendar date. FK to dim_dates.
        data_tests:
          - not_null

      - name: location_key
        data_type: string
        description: >-
          Surrogate key for the school. FK to dim_locations.
        data_tests:
          - not_null

      - name: is_in_session
        data_type: boolean
        description: >-
          TRUE if this date is an instructional day at this school.

      - name: is_membership_day
        data_type: boolean
        description: >-
          TRUE if this date counts toward student membership at this school.
```

- [ ] **Step 2: Write SQL model**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql`:

```sql
select
    cd.date_value as date_key,

    {{ dbt_utils.generate_surrogate_key(["loc.location_clean_name"]) }}
    as location_key,

    cd.insession = 1 as is_in_session,
    cd.membershipvalue > 0 as is_membership_day,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join {{ ref("int_people__location_crosswalk") }} as loc
    on cd.schoolid = loc.location_powerschool_school_id
    and {{ union_dataset_join_clause(left_alias="cd", right_alias="loc") }}
where
    not loc.location_is_pathways
    and loc.location_clean_name <> 'KIPP Whittier Elementary'
```

**Note:** The `location_key` surrogate must match `dim_locations` exactly — both
derive from `location_clean_name` using `generate_surrogate_key`. The join to
`int_people__location_crosswalk` resolves `schoolid` → `location_clean_name` and
filters to the same set of locations as `dim_locations`. The
`union_dataset_join_clause` macro is required because both
`stg_powerschool__calendar_day` and `int_people__location_crosswalk` are union
models carrying `_dbt_source_relation`.

- [ ] **Step 3: Build and test**

```bash
uv run dbt build -s dim_school_calendars --project-dir src/dbt/kipptaf
```

Expected: model builds as a view, unique combination test on
`(date_key, location_key)` passes, not_null tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_school_calendars.yml
git commit -m "feat(marts): add dim_school_calendars conformed dimension"
```

---

### Task 6: Cleanup old prototype files

Remove the old prototype models from `models/marts/` that have been replaced by
the new versions in `models/marts/dimensions/`. The old files must be removed so
dbt does not find duplicate model names.

**Files to delete:**

- `models/marts/dim_dates.sql`
- `models/marts/properties/dim_dates.yml`
- `models/marts/dim_terms.sql`
- `models/marts/properties/dim_terms.yml`
- `models/marts/dim_locations.sql`
- `models/marts/properties/dim_locations.yml`

- [ ] **Step 1: Delete old files**

```bash
git rm src/dbt/kipptaf/models/marts/dim_dates.sql src/dbt/kipptaf/models/marts/properties/dim_dates.yml
git rm src/dbt/kipptaf/models/marts/dim_terms.sql src/dbt/kipptaf/models/marts/properties/dim_terms.yml
git rm src/dbt/kipptaf/models/marts/dim_locations.sql src/dbt/kipptaf/models/marts/properties/dim_locations.yml
```

- [ ] **Step 2: Verify no duplicate model names**

```bash
uv run dbt ls -s dim_dates dim_terms dim_locations dim_regions dim_school_calendars --project-dir src/dbt/kipptaf
```

Expected: each model name appears exactly once, all pointing to the
`models/marts/dimensions/` path.

- [ ] **Step 3: Build all 5 conformed dimensions together**

```bash
uv run dbt build -s dim_dates dim_regions dim_terms dim_locations dim_school_calendars --project-dir src/dbt/kipptaf
```

Expected: all 5 models build and all tests pass.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor(marts): remove old prototype conformed dimensions"
```

---

## Verification checklist

After all tasks are complete, verify:

- [ ] `models/marts/dimensions/` contains exactly 5 `.sql` files: `dim_dates`,
      `dim_regions`, `dim_terms`, `dim_locations`, `dim_school_calendars`
- [ ] `models/marts/dimensions/properties/` contains exactly 5 `.yml` files
- [ ] No `dim_*` files remain in `models/marts/` root (other prototype
      `dim_staff`, `dim_students`, etc. will be handled in later plans)
- [ ] `uv run dbt build -s dim_dates dim_regions dim_terms dim_locations dim_school_calendars`
      passes with all tests green
- [ ] `dim_dates` is materialized as `table` (config in YAML)
- [ ] All other conformed dims are materialized as `view` (directory default)
- [ ] Every model has a uniqueness test on its primary key
- [ ] `dim_school_calendars` has a compound uniqueness test on
      `(date_key, location_key)`
- [ ] No source-system or KIPP-specific column names leak into the mart (generic
      naming throughout)
