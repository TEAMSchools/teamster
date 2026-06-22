# Focus Staging — Attendance Lookups (Batch C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the four
populated Focus attendance-lookup tables (`attendance_codes`,
`attendance_completed`, `marking_periods`, `school_periods`) in the `focus`
source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
uniqueness test on each table's primary key, and a `description:` on the model
and every column. Models build inside the consuming district project
(`kippmiami`), which sets `focus_schema` and imports the `focus` package.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, dbt contracts. SQL per
`.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas, single quotes, 88
cols, lowercase).

## Global Constraints

- Contract enforcement is already set at the `staging` directory level in
  `src/dbt/focus/dbt_project.yml` (`+contract: enforced: true`) — do NOT add
  `{{ config(contract=...) }}` per model. Every column the SQL projects MUST be
  declared in the properties YAML with a matching `data_type`.
- Source is BQ-native: `{{ source("focus", "<table>") }}` (source name `focus`,
  bare table name). Schema resolves from `var("focus_schema")` =
  `dagster_kippmiami_dlt_focus` (set in `src/dbt/kippmiami/dbt_project.yml`).
- Exclude dlt bookkeeping columns (`_dlt_id`, `_dlt_load_id`) and the audit-quad
  (`created_by_class`, `created_by_id`, `updated_by_class`, `updated_by_id`)
  from every model. Keep `created_at` / `updated_at` / `uuid`.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`).
- These four tables have NO soft-delete column and NO `BOOL` columns, so no
  `where deleted = 0` filter and no `is_` boolean conversion in this batch.
  Y/N-style flags stay raw `STRING` (convert in an intermediate layer later if a
  consumer needs it).
- Focus columns are already `snake_case`; no reserved-word columns in these four
  tables, so no backtick-quoting / `quote: true`.
- Build/test context is the **kippmiami** project, not `focus` standalone.

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__attendance_codes`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__attendance_codes.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__attendance_codes.yml`

**Interfaces:**

- Consumes: `source("focus", "attendance_codes")`
- Produces: model `stg_focus__attendance_codes`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    type,
    state_code,
    default_code,
    table_name,
    sort_order,
    is_daily_code,
    excused,
    tardy,
    discipline,
    not_in_class,
    denies_credit,
    chronic_absenteeism,
    truancy,
    out_of_school,
    state_attendance_type,
    color,
    sub,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "attendance_codes") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__attendance_codes
    description: >-
      Focus attendance code definitions — one row per attendance code, scoped by
      school year and school. Lookup for daily and period attendance marks.
    columns:
      - name: id
        description: Primary key — Focus attendance code id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: syear
        description: Focus school year (start year, e.g. 2025 = 2025-26).
        data_type: int
      - name: school_id
        description: Focus school id the code belongs to.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full attendance code name.
        data_type: string
      - name: short_name
        description: Abbreviated attendance code label.
        data_type: string
      - name: type
        description: Attendance code type classification.
        data_type: string
      - name: state_code
        description: State-reporting code mapped to this attendance code.
        data_type: string
      - name: default_code
        description: Flag — whether this is the default code for its context.
        data_type: string
      - name: table_name
        description: Legacy Focus internal grouping value.
        data_type: numeric
      - name: sort_order
        description: Display sort order within the code list.
        data_type: numeric
      - name: is_daily_code
        description: Y/N — whether the code applies to daily attendance.
        data_type: string
      - name: excused
        description: Y/N — whether the code counts as an excused absence.
        data_type: string
      - name: tardy
        description: Y/N — whether the code represents a tardy.
        data_type: string
      - name: discipline
        description: Y/N — whether the code is discipline-related.
        data_type: string
      - name: not_in_class
        description: Y/N — whether the student is counted as not in class.
        data_type: string
      - name: denies_credit
        description: Y/N — whether the code denies course credit.
        data_type: string
      - name: chronic_absenteeism
        description: Y/N — whether the code counts toward chronic absenteeism.
        data_type: string
      - name: truancy
        description: Y/N — whether the code counts toward truancy.
        data_type: string
      - name: out_of_school
        description: Y/N — whether the code represents an out-of-school absence.
        data_type: string
      - name: state_attendance_type
        description: State-reporting attendance type for this code.
        data_type: string
      - name: color
        description: UI display color for the code.
        data_type: string
      - name: sub
        description: Legacy Focus sub-classification value.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__attendance_codes --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `id` PASS. A contract
mismatch here means a `data_type` in the YAML disagrees with the warehouse — fix
the YAML to match `INFORMATION_SCHEMA.COLUMNS`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__attendance_codes.sql src/dbt/focus/models/staging/properties/stg_focus__attendance_codes.yml
git commit -m "feat(dbt): add stg_focus__attendance_codes (#4213)"
```

---

### Task 2: `stg_focus__attendance_completed`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__attendance_completed.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__attendance_completed.yml`

**Interfaces:**

- Consumes: `source("focus", "attendance_completed")`
- Produces: model `stg_focus__attendance_completed`, grain one row per `id` (a
  teacher's attendance-taken record for a section on a date).

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    staff_id,
    period_id,
    course_period_id,
    school_date,
    attendance_taken_same_day,
    last_updated_date,
    created_at,
    updated_at,
from {{ source("focus", "attendance_completed") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__attendance_completed
    description: >-
      Focus attendance-completion records — one row per section per date marking
      that a teacher submitted attendance.
    columns:
      - name: id
        description: Primary key — Focus attendance-completed id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: staff_id
        description: Focus staff id of the teacher who took attendance.
        data_type: int
      - name: period_id
        description: Focus school period id.
        data_type: int
      - name: course_period_id
        description: Focus course-period (section) id.
        data_type: int
      - name: school_date
        description: Calendar date the attendance was taken for.
        data_type: date
      - name: attendance_taken_same_day
        description: Y/N — whether attendance was submitted on the school date.
        data_type: string
      - name: last_updated_date
        description: Source last-updated timestamp.
        data_type: timestamp
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__attendance_completed --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__attendance_completed.sql src/dbt/focus/models/staging/properties/stg_focus__attendance_completed.yml
git commit -m "feat(dbt): add stg_focus__attendance_completed (#4213)"
```

---

### Task 3: `stg_focus__marking_periods`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__marking_periods.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__marking_periods.yml`

**Interfaces:**

- Consumes: `source("focus", "marking_periods")`
- Produces: model `stg_focus__marking_periods`, grain one row per
  `marking_period_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    marking_period_id,
    parent_id,
    rollover_id,
    school_id,
    syear,
    title,
    short_name,
    type,
    sort_order,
    year_fraction,
    tuition_hours,
    year_id,
    semester_id,
    quarter_id,
    progress_period_id,
    start_date,
    end_date,
    post_start_date,
    post_end_date,
    stand_post_start_date,
    stand_post_end_date,
    grade12_post_start_date,
    grade12_post_end_date,
    registration_start_date,
    registration_end_date,
    exclude_from_api,
    exclude_from_schedule,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "marking_periods") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__marking_periods
    description: >-
      Focus marking periods (terms) — one row per marking period, including the
      term hierarchy (year/semester/quarter/progress) and posting windows.
    columns:
      - name: marking_period_id
        description: Primary key — Focus marking period id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: parent_id
        description: Parent marking period id in the term hierarchy.
        data_type: int
      - name: rollover_id
        description: Source marking period id this rolled over from.
        data_type: int
      - name: school_id
        description: Focus school id.
        data_type: int
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: title
        description: Full marking period name.
        data_type: string
      - name: short_name
        description: Abbreviated marking period label.
        data_type: string
      - name: type
        description:
          Marking period type (e.g. year, semester, quarter, progress).
        data_type: string
      - name: sort_order
        description: Display sort order.
        data_type: numeric
      - name: year_fraction
        description: Fraction of the school year this period represents.
        data_type: numeric
      - name: tuition_hours
        description: Tuition hours associated with the period.
        data_type: int
      - name: year_id
        description: Enclosing year marking period id.
        data_type: int
      - name: semester_id
        description: Enclosing semester marking period id.
        data_type: int
      - name: quarter_id
        description: Enclosing quarter marking period id.
        data_type: int
      - name: progress_period_id
        description: Enclosing progress period marking period id.
        data_type: int
      - name: start_date
        description: First date of the marking period.
        data_type: date
      - name: end_date
        description: Last date of the marking period.
        data_type: date
      - name: post_start_date
        description: Grade-posting window open date.
        data_type: date
      - name: post_end_date
        description: Grade-posting window close timestamp.
        data_type: timestamp
      - name: stand_post_start_date
        description: Standards grade-posting window open date.
        data_type: date
      - name: stand_post_end_date
        description: Standards grade-posting window close timestamp.
        data_type: timestamp
      - name: grade12_post_start_date
        description: Grade-12 posting window open date.
        data_type: date
      - name: grade12_post_end_date
        description: Grade-12 posting window close timestamp.
        data_type: timestamp
      - name: registration_start_date
        description: Registration window open date.
        data_type: date
      - name: registration_end_date
        description: Registration window close date.
        data_type: date
      - name: exclude_from_api
        description: Y/N — whether the period is excluded from the Focus API.
        data_type: string
      - name: exclude_from_schedule
        description: Y/N — whether the period is excluded from scheduling.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__marking_periods --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `marking_period_id` PASS. Watch the
mixed `date` vs `timestamp` posting columns — match the YAML `data_type` to the
warehouse type shown above exactly, or the contract fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__marking_periods.sql src/dbt/focus/models/staging/properties/stg_focus__marking_periods.yml
git commit -m "feat(dbt): add stg_focus__marking_periods (#4213)"
```

---

### Task 4: `stg_focus__school_periods`

`school_periods` has 64 columns, 52 of them per-weekday `length_*` /
`start_time_*` / `end_time_*` variants that no downstream layer needs. Curate to
the canonical period definition; the per-weekday columns are dropped
(recoverable later if a scheduling consumer ever needs them).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__school_periods.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__school_periods.yml`

**Interfaces:**

- Consumes: `source("focus", "school_periods")`
- Produces: model `stg_focus__school_periods`, grain one row per `period_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    period_id,
    rollover_id,
    school_id,
    district_id,
    syear,
    title,
    short_name,
    block,
    attendance,
    required_for_scheduling,
    conflicts_with,
    sort_order,
    length,
    start_time,
    end_time,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "school_periods") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__school_periods
    description: >-
      Focus school periods — one row per period definition per school year. The
      canonical period plus its default start/end time; per-weekday time and
      length variants are intentionally excluded.
    columns:
      - name: period_id
        description: Primary key — Focus school period id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: rollover_id
        description: Source period id this rolled over from.
        data_type: int
      - name: school_id
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: title
        description: Full period name.
        data_type: string
      - name: short_name
        description: Abbreviated period label.
        data_type: string
      - name: block
        description: Block identifier the period belongs to.
        data_type: string
      - name: attendance
        description: Y/N — whether attendance is taken in this period.
        data_type: string
      - name: required_for_scheduling
        description: Y/N — whether the period is required when scheduling.
        data_type: string
      - name: conflicts_with
        description: Period ids this period conflicts with for scheduling.
        data_type: string
      - name: sort_order
        description: Display sort order.
        data_type: numeric
      - name: length
        description: Default period length in minutes.
        data_type: numeric
      - name: start_time
        description: Default period start time.
        data_type: time
      - name: end_time
        description: Default period end time.
        data_type: time
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__school_periods --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `period_id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__school_periods.sql src/dbt/focus/models/staging/properties/stg_focus__school_periods.yml
git commit -m "feat(dbt): add stg_focus__school_periods (#4213)"
```

---

## Final verification

- [ ] **Build all four together:**

```bash
uv run dbt build --select stg_focus__attendance_codes stg_focus__attendance_completed stg_focus__marking_periods stg_focus__school_periods --project-dir src/dbt/kippmiami
```

Expected: 4 models build, 8 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook):

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__attendance_codes.sql \
  src/dbt/focus/models/staging/stg_focus__attendance_completed.sql \
  src/dbt/focus/models/staging/stg_focus__marking_periods.sql \
  src/dbt/focus/models/staging/stg_focus__school_periods.sql \
  src/dbt/focus/models/staging/properties/stg_focus__attendance_codes.yml \
  src/dbt/focus/models/staging/properties/stg_focus__attendance_completed.yml \
  src/dbt/focus/models/staging/properties/stg_focus__marking_periods.yml \
  src/dbt/focus/models/staging/properties/stg_focus__school_periods.yml
```

(Run from inside the worktree.)

## Out of scope (other plans / issues)

- Intermediate models for daily/period attendance — source tables
  (`attendance_day`, `attendance_period`) are empty (#4220).
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all four populated attendance-lookup tables have a staging
   task. ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command. ✓
3. **Type consistency:** each YAML `data_type` matches the warehouse type pulled
   from `INFORMATION_SCHEMA.COLUMNS` (int/string/numeric/date/time/timestamp).
   Re-verify `marking_periods` date-vs-timestamp posting columns during build.
