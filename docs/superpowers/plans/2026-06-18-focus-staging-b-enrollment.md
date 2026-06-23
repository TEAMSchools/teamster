# Focus Staging — Enrollment & Org (Batch B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the seven
populated Focus enrollment/org tables (`student_enrollment`,
`student_enrollment_codes`, `school_gradelevels`, `schools`, `districts`,
`attendance_calendars`, `grad_subject_programs`) plus one intermediate model
(`int_focus__student_enrollment`) that joins enrollment to its school, grade
level, and enrollment code.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns),
soft-delete filtering where the table carries a `deleted` flag, a uniqueness
test on each table's primary key, and a `description:` on the model and every
column. The two WIDE tables (`schools`, `student_enrollment`) additionally carry
an inline "populated custom fields" block — every Focus `custom_*` column that
holds at least one non-null value in the current Miami pull, projected
`<raw> as <slug>` after the curated core. A new `intermediate/` layer adds
`int_focus__student_enrollment`, a many-to-one enrichment of enrollment rows
with school, grade-level, and enrollment-code attributes. Models build inside
the consuming district project (`kippmiami`), which sets `focus_schema` and
imports the `focus` package.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, dbt contracts. SQL per
`.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas, single quotes, 88
cols, lowercase).

## Global Constraints

- Contract enforcement is set at the `staging` directory level in
  `src/dbt/focus/dbt_project.yml` (`+contract: enforced: true`) — do NOT add
  `{{ config(contract=...) }}` per staging model. Every column the staging SQL
  projects MUST be declared in the properties YAML with a matching `data_type`.
- The **intermediate layer is NOT contract-enforced** (the project config
  enforces contracts only under `staging`). `int_focus__student_enrollment`
  therefore does NOT need a `data_type:` on every column — it needs a
  `description:` on the model and every column plus a uniqueness test
  (`src/dbt/CLAUDE.md` → "All intermediate models must").
- Source is BQ-native: `{{ source("focus", "<table>") }}` (source name `focus`,
  bare table name). Schema resolves from `var("focus_schema")` =
  `dagster_kippmiami_dlt_focus` (set in `src/dbt/kippmiami/dbt_project.yml`).
- Exclude dlt bookkeeping columns (`_dlt_*`) and the audit-quad
  (`created_by_class`, `created_by_id`, `updated_by_class`, `updated_by_id`)
  from every model. Keep `created_at` / `updated_at` / `uuid`.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`).
- **Soft-delete filter:** In this Miami Focus dataset, the `deleted` column on
  `schools` and `student_enrollment_codes` is `NULL` for live rows and `1` for
  deleted rows — NOT `0` for live. A `where deleted = 0` filter returns ZERO
  rows. Use `where deleted is null` (NULL = live) and OMIT the `deleted` column
  from the projection. The other five tables in this batch have no `deleted`
  column. (`districts`, `school_gradelevels`, `attendance_calendars`,
  `grad_subject_programs` carry an `active` / `rollover` / `default_calendar`
  STRING flag, NOT a delete flag — keep those raw.)
- **Populated custom fields (WIDE tables only — `schools`,
  `student_enrollment`):** project every Focus `custom_*` column that is
  populated (at least one non-null value) in the current Miami pull, aliased
  `<raw_column_name> as <slug>`, placed after the curated core columns and
  before any cast block (ST06). The authoritative set per table is the
  pre-generated map (`.claude/scratch/focus-<table>-custom-map.md`); each map
  row is `column_name | slug | bq_type | focus_type | populated_rows | title`.
  - Add a custom column ONLY if it appears in the map. Unpopulated `custom_*`
    columns (absent from the map) are OUT OF SCOPE for this batch.
  - Do NOT duplicate a column already projected elsewhere — the custom block is
    the single home for these `custom_*` columns; they are not also projected
    under a different alias.
  - **Values are left ENCODED.** `select` / `multiple` custom fields store an
    option code, not a decoded label. Do NOT decode them here — code-to-label
    decoding is a deferred follow-up. State this in the model description.
  - The raw `custom_fields` JSON blob (where present) is NOT projected; it is a
    separate concern and out of scope for this batch.
- Focus columns are already `snake_case`. The reserved word `type` appears as a
  column in `student_enrollment_codes` — BigQuery does NOT reserve `type`, so it
  needs no backtick / `quote: true` (confirmed against the four Batch C models,
  which carry a raw `type` column). `pk` (column on `school_gradelevels`) and
  `state` (column on `districts`) are likewise non-reserved in BigQuery and stay
  raw.
- Build/test context is the **kippmiami** project, not `focus` standalone.
  Command: `uv run dbt build --select <model> --project-dir src/dbt/kippmiami`.

## BigQuery type → YAML `data_type` mapping used below

Pulled verbatim from `INFORMATION_SCHEMA.COLUMNS` of
`dagster_kippmiami_dlt_focus`. Use these exact spellings in the contract YAML
(the contract matches name + type, not order):

- `INT64` → `data_type: int`
- `STRING` → `data_type: string`
- `NUMERIC` → `data_type: numeric`
- `DATE` → `data_type: date`
- `TIMESTAMP` → `data_type: timestamp`
- `TIME` → `data_type: time`
- `BOOL` → `data_type: boolean`

`int`/`int64`, `decimal`/`numeric`, `boolean`/`bool` are BQ synonyms; the
spellings above match the existing Batch C staging YAML.

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__districts`

`districts` has 27 columns (after excluding `_dlt_*`). Narrow table — keep all
non-excluded columns. PK is `id`. No soft-delete column (`active` is a STRING
status flag, kept raw). `seperate_site` is `BOOL` → `data_type: boolean`.
`custom_fields` (raw JSON blob) and the per-district `custom_l1277` are kept as
opaque STRING pass-throughs (this narrow table has no separate populated-custom
block — the inline custom-field treatment applies only to the WIDE tables,
`schools` and `student_enrollment`).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__districts.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__districts.yml`

**Interfaces:**

- Consumes: `source("focus", "districts")`
- Produces: model `stg_focus__districts`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    district_element_id,
    paec_school_nurse_profile,
    logo_width,
    logo_height,
    code,
    title,
    short_name,
    address,
    city,
    state,
    district_element,
    active,
    logo,
    custom_fields,
    custom_l1277,
    paec_transcript_message,
    paec_transcript_logo,
    paec_transcript_signature,
    uuid,
    seperate_site,
    created_at,
    updated_at,
from {{ source("focus", "districts") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__districts
    description: >-
      Focus district records — one row per district. Carries district codes,
      address, and PAEC transcript branding settings.
    columns:
      - name: id
        description: Primary key — Focus district id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: district_element_id
        description: Focus district element id.
        data_type: int
      - name: paec_school_nurse_profile
        description: Profile id of the PAEC school nurse.
        data_type: int
      - name: logo_width
        description: District logo width in pixels.
        data_type: string
      - name: logo_height
        description: District logo height in pixels.
        data_type: string
      - name: code
        description: District code.
        data_type: string
      - name: title
        description: Full district name.
        data_type: string
      - name: short_name
        description: Abbreviated district label.
        data_type: string
      - name: address
        description: District street address.
        data_type: string
      - name: city
        description: District city.
        data_type: string
      - name: state
        description: District state.
        data_type: string
      - name: district_element
        description: Focus district element value.
        data_type: int
      - name: active
        description: Y/N — whether the district is active.
        data_type: string
      - name: logo
        description: District logo file reference.
        data_type: string
      - name: custom_fields
        description: >-
          Raw Focus custom-fields JSON blob; structured values are out of scope
          for this batch.
        data_type: string
      - name: custom_l1277
        description: Focus custom field l1277 (district-specific).
        data_type: string
      - name: paec_transcript_message
        description: PAEC transcript message text.
        data_type: string
      - name: paec_transcript_logo
        description: PAEC transcript logo reference.
        data_type: string
      - name: paec_transcript_signature
        description: PAEC transcript signature reference.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: seperate_site
        description: >-
          Whether the district is configured as a separate site (Focus spelling
          preserved).
        data_type: boolean
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__districts --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS. A contract mismatch
means a `data_type` disagrees with the warehouse — fix the YAML to match
`INFORMATION_SCHEMA.COLUMNS`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__districts.sql src/dbt/focus/models/staging/properties/stg_focus__districts.yml
git commit -m "feat(dbt): add stg_focus__districts (#4213)"
```

---

### Task 2: `stg_focus__schools` (WIDE — curated core + populated customs)

`schools` has 85 columns (after excluding `_dlt_*`), 56 of them `custom_*`
fields. Curate the non-custom core to: the natural/foreign keys (`id`,
`district_id`, `state_school_id`, `erp_facility_id`), the school-year bounds
(`min_syear` / `max_syear`), `title`, geo (`latitude` / `longitude`),
`sort_order`, the ACT/College-Board codes, the `virtual` flag, and audit
timestamps + `uuid`.

**Populated custom fields (inline block):** the eight `custom_*` columns that
are populated in the current Miami pull, per
`.claude/scratch/focus-schools-custom-map.md`. Each is projected
`<raw> as <slug>` after the core, before any cast block. The other 48 `custom_*`
columns are unpopulated and OUT OF SCOPE. Values are left as stored codes — the
`select`-type customs (`school_level`, `school_type`, `technical_center`) carry
Focus option codes, not decoded labels; decoding is a deferred follow-up. The
raw `custom_fields` JSON blob is not projected.

**Soft-delete:** `deleted` is `NULL` for live rows here (NOT `0`) — filter
`where deleted is null` and OMIT `deleted`.

**Populated-custom map (verbatim from the scratch map file):**

| raw column         | slug                           | bq_type | focus_type | title                        |
| ------------------ | ------------------------------ | ------- | ---------- | ---------------------------- |
| `custom_327`       | `school_number`                | STRING  | text       | School Number                |
| `custom_100000001` | `district_number`              | STRING  | text       | District Number              |
| `custom_100000004` | `school_level`                 | INT64   | select     | School Level                 |
| `custom_200000321` | `state`                        | STRING  | text       | State                        |
| `custom_200000326` | `school_type`                  | INT64   | select     | School Type                  |
| `custom_50000002`  | `technical_center`             | INT64   | select     | Technical Center             |
| `custom_319000052` | `custom_319000052`             | STRING  | None       | (none)                       |
| `custom_200000200` | `exclude_from_state_reporting` | STRING  | checkbox   | Exclude from State Reporting |

`school_level` / `school_type` / `technical_center` are `INT64`; the other five
are `STRING`. `custom_319000052` has no catalog title — its description uses the
generic-slot fallback. The `school` map's `state` slug (`custom_200000321`) is
distinct from the `districts` table's own raw `state` column — no collision,
they are different models.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__schools.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__schools.yml`

**Interfaces:**

- Consumes: `source("focus", "schools")`
- Produces: model `stg_focus__schools`, grain one row per `id`. The intermediate
  (Task 8) reads `id`, `title`, `state_school_id`.

- [ ] **Step 1: Write the model SQL**

ST06 — the curated core (plain refs) comes first, then the populated-custom
block (plain refs aliased `<raw> as <slug>`), then the audit columns. No casts
or functions are used, so there is no separate cast group.

```sql
select
    id,
    district_id,
    state_school_id,
    erp_facility_id,
    min_syear,
    max_syear,
    title,
    latitude,
    longitude,
    sort_order,
    act_organization_code,
    college_board_attending_institution_code,
    virtual,
    custom_327 as school_number,
    custom_100000001 as district_number,
    custom_100000004 as school_level,
    custom_200000321 as state,
    custom_200000326 as school_type,
    custom_50000002 as technical_center,
    custom_319000052,
    custom_200000200 as exclude_from_state_reporting,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "schools") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__schools
    description: >-
      Focus school records — one row per live school (rows flagged deleted are
      excluded). Carries the curated core plus every populated Focus custom
      field, each projected under a readable slug. Select / multiple custom
      values remain as stored Focus option codes — code-to-label decoding is a
      deferred follow-up. Unpopulated custom fields and the raw custom_fields
      JSON blob are out of scope for this batch.
    columns:
      - name: id
        description: Primary key — Focus school id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: district_id
        description: Focus district id the school belongs to.
        data_type: int
      - name: state_school_id
        description: State-assigned school id.
        data_type: int
      - name: erp_facility_id
        description: ERP facility id mapped to the school.
        data_type: int
      - name: min_syear
        description: Earliest school year (start year) the school is active.
        data_type: int
      - name: max_syear
        description: Latest school year (start year) the school is active.
        data_type: int
      - name: title
        description: Full school name.
        data_type: string
      - name: latitude
        description: School latitude.
        data_type: numeric
      - name: longitude
        description: School longitude.
        data_type: numeric
      - name: sort_order
        description: Display sort order in the school list.
        data_type: numeric
      - name: act_organization_code
        description: ACT organization (high school) code.
        data_type: numeric
      - name: college_board_attending_institution_code
        description: College Board attending-institution code.
        data_type: string
      - name: virtual
        description: Y/N — whether the school is virtual.
        data_type: string
      - name: school_number
        description: >-
          School Number. Populated Focus custom field (custom_327); stored value
          left as-is.
        data_type: string
      - name: district_number
        description: >-
          District Number. Populated Focus custom field (custom_100000001);
          stored value left as-is.
        data_type: string
      - name: school_level
        description: >-
          School Level. Populated Focus custom field (custom_100000004) of type
          select; stored as the Focus option code, not a decoded label.
        data_type: int
      - name: state
        description: >-
          State. Populated Focus custom field (custom_200000321); stored value
          left as-is.
        data_type: string
      - name: school_type
        description: >-
          School Type. Populated Focus custom field (custom_200000326) of type
          select; stored as the Focus option code, not a decoded label.
        data_type: int
      - name: technical_center
        description: >-
          Technical Center. Populated Focus custom field (custom_50000002) of
          type select; stored as the Focus option code, not a decoded label.
        data_type: int
      - name: custom_319000052
        description: >-
          Focus generic custom slot; label not defined in the extracted
          custom_fields catalog.
        data_type: string
      - name: exclude_from_state_reporting
        description: >-
          Exclude from State Reporting. Populated Focus custom field
          (custom_200000200) of type checkbox; stored value left as-is.
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
`uv run dbt build --select stg_focus__schools --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS. The model returns
only live rows (10 in the current Miami pull). Watch the `int` vs `string` split
on the custom block — `school_level` (`custom_100000004`), `school_type`
(`custom_200000326`), and `technical_center` (`custom_50000002`) are `INT64`;
the other five customs are `STRING`. Match the YAML exactly or the contract
fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__schools.sql src/dbt/focus/models/staging/properties/stg_focus__schools.yml
git commit -m "feat(dbt): add stg_focus__schools (#4213)"
```

---

### Task 3: `stg_focus__school_gradelevels`

`school_gradelevels` has 23 columns (after excluding `_dlt_*`). Narrow table —
keep all non-excluded columns. PK is `id`. No soft-delete column (`rollover` /
`zoning` / `pk` are STRING flags, kept raw). `pk` is a Y/N flag (pre-K
indicator), NOT a key, and is non-reserved in BigQuery.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__school_gradelevels.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__school_gradelevels.yml`

**Interfaces:**

- Consumes: `source("focus", "school_gradelevels")`
- Produces: model `stg_focus__school_gradelevels`, grain one row per `id`.
  Consumed by `int_focus__student_enrollment` (Task 8) on `id = grade_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    school_id,
    next_grade_id,
    rollover_id,
    min_year,
    max_year,
    district_id,
    short_name,
    title,
    sort_order,
    min_syear,
    max_syear,
    rollover,
    uuid,
    zoning,
    choice_short_name,
    pk,
    created_at,
    updated_at,
from {{ source("focus", "school_gradelevels") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__school_gradelevels
    description: >-
      Focus grade-level definitions — one row per grade level per school. Maps a
      grade-level id to its title, school, and rollover linkage.
    columns:
      - name: id
        description: Primary key — Focus grade-level id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: school_id
        description: Focus school id the grade level belongs to.
        data_type: int
      - name: next_grade_id
        description: Grade-level id a student rolls into the next year.
        data_type: int
      - name: rollover_id
        description: Source grade-level id this rolled over from.
        data_type: int
      - name: min_year
        description: Earliest calendar year the grade level is active.
        data_type: int
      - name: max_year
        description: Latest calendar year the grade level is active.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: short_name
        description: Abbreviated grade-level label.
        data_type: string
      - name: title
        description: Full grade-level name.
        data_type: string
      - name: sort_order
        description: Display sort order within the school's grade levels.
        data_type: numeric
      - name: min_syear
        description:
          Earliest school year (start year) the grade level is active.
        data_type: numeric
      - name: max_syear
        description: Latest school year (start year) the grade level is active.
        data_type: numeric
      - name: rollover
        description: Y/N — whether the grade level participates in rollover.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: zoning
        description: Y/N — whether zoning applies to the grade level.
        data_type: string
      - name: choice_short_name
        description: Abbreviated label used for school-choice reporting.
        data_type: string
      - name: pk
        description: Y/N — whether the grade level is pre-kindergarten.
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
`uv run dbt build --select stg_focus__school_gradelevels --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS (75 rows in current
pull). Watch `min_syear` / `max_syear` here are `NUMERIC` (not `INT64` like on
`schools`) — match `data_type: numeric`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__school_gradelevels.sql src/dbt/focus/models/staging/properties/stg_focus__school_gradelevels.yml
git commit -m "feat(dbt): add stg_focus__school_gradelevels (#4213)"
```

---

### Task 4: `stg_focus__student_enrollment_codes`

`student_enrollment_codes` has 19 columns (after excluding `_dlt_*`). Narrow
table — keep all non-excluded columns except the soft-delete flag. PK is `id`.
**Soft-delete:** `deleted` is `NULL` for live rows here (NOT `0`) — filter
`where deleted is null` and OMIT `deleted`. `type` is a raw STRING column and is
non-reserved in BigQuery (no backtick / `quote: true`).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__student_enrollment_codes.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__student_enrollment_codes.yml`

**Interfaces:**

- Consumes: `source("focus", "student_enrollment_codes")`
- Produces: model `stg_focus__student_enrollment_codes`, grain one row per `id`.
  Consumed by `int_focus__student_enrollment` (Task 8) on
  `id = enrollment_code`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    min_syear,
    max_syear,
    district_id,
    title,
    short_name,
    type,
    profile_ids,
    gradelevels,
    grad_type,
    sort_order,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "student_enrollment_codes") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__student_enrollment_codes
    description: >-
      Focus enrollment / withdrawal code definitions — one row per live code
      (rows flagged deleted are excluded). Lookup for the enrollment_code and
      drop_code on student_enrollment.
    columns:
      - name: id
        description: Primary key — Focus enrollment-code id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: min_syear
        description: Earliest school year (start year) the code is valid.
        data_type: int
      - name: max_syear
        description: Latest school year (start year) the code is valid.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full enrollment-code name.
        data_type: string
      - name: short_name
        description: Abbreviated enrollment-code label.
        data_type: string
      - name: type
        description: >-
          Code classification — distinguishes enrollment vs withdrawal codes.
        data_type: string
      - name: profile_ids
        description: Comma-delimited profile ids permitted to use the code.
        data_type: string
      - name: gradelevels
        description: Comma-delimited grade-level ids the code applies to.
        data_type: string
      - name: grad_type
        description: Graduation type associated with the code.
        data_type: string
      - name: sort_order
        description: Display sort order within the code list.
        data_type: numeric
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
`uv run dbt build --select stg_focus__student_enrollment_codes --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS. The model returns
only live rows (152 in the current Miami pull, of 1595 total — the 1443
`deleted = 1` rows are excluded).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__student_enrollment_codes.sql src/dbt/focus/models/staging/properties/stg_focus__student_enrollment_codes.yml
git commit -m "feat(dbt): add stg_focus__student_enrollment_codes (#4213)"
```

---

### Task 5: `stg_focus__attendance_calendars`

`attendance_calendars` has 15 columns (after excluding `_dlt_*`). Narrow table —
keep all non-excluded columns. PK is `calendar_id` (this table has NO `id`
column; `calendar_id` is the natural key). No soft-delete column
(`default_calendar` / `imported` are STRING flags, kept raw).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__attendance_calendars.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__attendance_calendars.yml`

**Interfaces:**

- Consumes: `source("focus", "attendance_calendars")`
- Produces: model `stg_focus__attendance_calendars`, grain one row per
  `calendar_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    calendar_id,
    school_id,
    syear,
    rollover_id,
    district_id,
    title,
    default_calendar,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "attendance_calendars") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__attendance_calendars
    description: >-
      Focus attendance calendars — one row per calendar per school year. Lookup
      for the calendar_id referenced by student_enrollment.
    columns:
      - name: calendar_id
        description: Primary key — Focus attendance calendar id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: school_id
        description: Focus school id the calendar belongs to.
        data_type: int
      - name: syear
        description: Focus school year (start year, e.g. 2025 = 2025-26).
        data_type: int
      - name: rollover_id
        description: Source calendar id this rolled over from.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full calendar name.
        data_type: string
      - name: default_calendar
        description: Y/N — whether this is the school's default calendar.
        data_type: string
      - name: imported
        description: Y/N — whether the calendar was imported.
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
`uv run dbt build --select stg_focus__attendance_calendars --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `calendar_id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__attendance_calendars.sql src/dbt/focus/models/staging/properties/stg_focus__attendance_calendars.yml
git commit -m "feat(dbt): add stg_focus__attendance_calendars (#4213)"
```

---

### Task 6: `stg_focus__grad_subject_programs`

`grad_subject_programs` has 22 columns (after excluding `_dlt_*`). Narrow table
— keep all non-excluded columns. PK is `id`. No soft-delete column (the `hide_*`
/ `cte` / `weight_by_credits` columns are STRING flags, kept raw). `schools`
here is a STRING column (comma-delimited school-id list), NOT a key.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__grad_subject_programs.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__grad_subject_programs.yml`

**Interfaces:**

- Consumes: `source("focus", "grad_subject_programs")`
- Produces: model `stg_focus__grad_subject_programs`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    school_id,
    rollover_id,
    district_id,
    min_syear,
    max_syear,
    title,
    short_name,
    default_category,
    sort_order,
    weight_by_credits,
    cte,
    hide_merit,
    hide_biliteracy,
    hide_scholar,
    hide_header,
    hide_industry,
    hide_finearts,
    hide_ag,
    schools,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "grad_subject_programs") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__grad_subject_programs
    description: >-
      Focus graduation subject programs — one row per program. Defines the
      graduation-requirement program a student enrollment can be assigned to.
    columns:
      - name: id
        description: Primary key — Focus grad subject program id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: school_id
        description: Focus school id the program belongs to.
        data_type: int
      - name: rollover_id
        description: Source program id this rolled over from.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: min_syear
        description: Earliest school year (start year) the program is active.
        data_type: int
      - name: max_syear
        description: Latest school year (start year) the program is active.
        data_type: int
      - name: title
        description: Full program name.
        data_type: string
      - name: short_name
        description: Abbreviated program label.
        data_type: string
      - name: default_category
        description: Default subject category for the program.
        data_type: string
      - name: sort_order
        description: Display sort order.
        data_type: numeric
      - name: weight_by_credits
        description: Y/N — whether the program weights GPA by credits.
        data_type: string
      - name: cte
        description:
          Y/N — whether the program is career and technical education.
        data_type: string
      - name: hide_merit
        description: Y/N — whether the merit seal is hidden for the program.
        data_type: string
      - name: hide_biliteracy
        description: Y/N — whether the biliteracy seal is hidden.
        data_type: string
      - name: hide_scholar
        description: Y/N — whether the scholar designation is hidden.
        data_type: string
      - name: hide_header
        description: Y/N — whether the program header is hidden.
        data_type: string
      - name: hide_industry
        description: Y/N — whether the industry certification is hidden.
        data_type: string
      - name: hide_finearts
        description: Y/N — whether the fine-arts designation is hidden.
        data_type: string
      - name: hide_ag
        description: Y/N — whether the agriculture designation is hidden.
        data_type: string
      - name: schools
        description: Comma-delimited list of school ids the program applies to.
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
`uv run dbt build --select stg_focus__grad_subject_programs --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__grad_subject_programs.sql src/dbt/focus/models/staging/properties/stg_focus__grad_subject_programs.yml
git commit -m "feat(dbt): add stg_focus__grad_subject_programs (#4213)"
```

---

### Task 7: `stg_focus__student_enrollment` (WIDE — curated core + populated customs)

`student_enrollment` has 62 columns (after excluding `_dlt_*`). Curate the
non-custom core to: the keys (`id`, `school_id`, `student_id`, `grade_id`,
`enrollment_code`, `drop_code`, `calendar_id`, `graduation_requirement_program`,
`next_school`, `program_id`, `next_year_program_id`, `team_id`,
`progression_plan_category`, `hs_progression_plan_category`,
`planned_high_school`, `rollover_id`), `syear`, the dates (`start_date` /
`end_date`), the FLDOE state-reporting day counts (`fl_days_present` /
`fl_days_absent` / `fl_days_absent_not_disc`), the non-custom mapped fields
(`include_in_class_rank`, `distance_from_school`, `next_grade`, `imported`,
`first_time_indicator`, `mid_year_promotion`), plus audit timestamps + `uuid`.
**No soft-delete column** on this table.

**Populated custom fields (inline block):** the five `custom_*` columns that are
populated in the current Miami pull, per
`.claude/scratch/focus-student_enrollment-custom-map.md`. Each is projected
`<raw> as <slug>` after the core, before any cast block. All five resolve to a
catalog title under source*class `StudentEnrollment` (join on
`lower(column_name)` — see `src/dbt/focus/CLAUDE.md`), so each is aliased to the
slugified title. The other 15
`custom*\*`columns are unpopulated and OUT OF SCOPE. All five are`STRING`; values are encoded `select`
option codes left as-is (decode deferred to Wave 2).

**Populated-custom map (verbatim from the scratch map file):**

| raw column | slug                        | bq_type | focus_type | populated_rows | title                     |
| ---------- | --------------------------- | ------- | ---------- | -------------- | ------------------------- |
| `custom_1` | `prior_district`            | STRING  | select     | 1276           | Prior District            |
| `custom_2` | `prior_state`               | STRING  | select     | 1276           | Prior State               |
| `custom_3` | `prior_country`             | STRING  | select     | 1276           | Prior Country             |
| `custom_6` | `student_offender_transfer` | STRING  | select     | 1276           | Student Offender Transfer |
| `custom_4` | `educational_choice`        | STRING  | select     | 158            | Educational Choice        |

Each slug differs from its raw `custom_N` name, so each is projected with an
explicit `as <slug>` alias (no AL09 self-alias concern).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__student_enrollment.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `source("focus", "student_enrollment")`
- Produces: model `stg_focus__student_enrollment`, grain one row per `id`.
  Consumed by `int_focus__student_enrollment` (Task 8) as the base table.

- [ ] **Step 1: Write the model SQL**

ST06 — the curated core (plain refs) first, then the populated-custom block
(each aliased `<raw> as <slug>`), then audit columns. No casts are used.

```sql
select
    id,
    syear,
    school_id,
    student_id,
    grade_id,
    enrollment_code,
    drop_code,
    calendar_id,
    next_school,
    graduation_requirement_program,
    program_id,
    next_year_program_id,
    team_id,
    progression_plan_category,
    hs_progression_plan_category,
    planned_high_school,
    rollover_id,
    start_date,
    end_date,
    include_in_class_rank,
    distance_from_school,
    next_grade,
    imported,
    first_time_indicator,
    mid_year_promotion,
    fl_days_present,
    fl_days_absent,
    fl_days_absent_not_disc,
    custom_1 as prior_district,
    custom_2 as prior_state,
    custom_3 as prior_country,
    custom_4 as educational_choice,
    custom_6 as student_offender_transfer,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "student_enrollment") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__student_enrollment
    description: >-
      Focus student enrollment spans — one row per enrollment record (a student
      at a school for a date range in a school year). Carries the curated core
      (keys, dates, FLDOE day counts) plus every populated Focus custom field,
      each aliased to its catalog title (prior_district, prior_state,
      prior_country, educational_choice, student_offender_transfer). Those are
      select-type custom values stored as encoded option codes — code-to-label
      decoding is a deferred follow-up. Unpopulated custom fields are out of
      scope for this batch.
    columns:
      - name: id
        description: Primary key — Focus student enrollment id.
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
        description: Focus school id of the enrollment.
        data_type: int
      - name: student_id
        description: Focus student id (local student id).
        data_type: int
      - name: grade_id
        description: Focus grade-level id (joins school_gradelevels.id).
        data_type: int
      - name: enrollment_code
        description: >-
          Focus enrollment-code id (joins student_enrollment_codes.id) — the
          code for entering the school.
        data_type: int
      - name: drop_code
        description: >-
          Focus withdrawal-code id (joins student_enrollment_codes.id) — the
          code for leaving the school.
        data_type: int
      - name: calendar_id
        description: Focus attendance calendar id (joins attendance_calendars).
        data_type: int
      - name: next_school
        description: Rolling-retention next-school option id.
        data_type: int
      - name: graduation_requirement_program
        description: Grad subject program id assigned to the enrollment.
        data_type: int
      - name: program_id
        description: Current program id for the enrollment.
        data_type: int
      - name: next_year_program_id
        description: Program id planned for the next school year.
        data_type: int
      - name: team_id
        description: Focus team id the enrollment is assigned to.
        data_type: int
      - name: progression_plan_category
        description: Progression plan category id.
        data_type: int
      - name: hs_progression_plan_category
        description: High-school progression plan category id.
        data_type: int
      - name: planned_high_school
        description: Planned high-school id.
        data_type: int
      - name: rollover_id
        description: Source enrollment id this rolled over from.
        data_type: int
      - name: start_date
        description: Enrollment start date.
        data_type: date
      - name: end_date
        description: Enrollment withdraw date.
        data_type: date
      - name: include_in_class_rank
        description: Y/N — whether the enrollment is included in class rank.
        data_type: string
      - name: distance_from_school
        description: Distance from the student's home to the school.
        data_type: numeric
      - name: next_grade
        description: Next grade level.
        data_type: string
      - name: imported
        description: Y/N — whether the enrollment was imported.
        data_type: string
      - name: first_time_indicator
        description: First-time enrollment indicator.
        data_type: string
      - name: mid_year_promotion
        description: Y/N — whether a mid-year promotion occurred.
        data_type: string
      - name: fl_days_present
        description: FLDOE days present.
        data_type: numeric
      - name: fl_days_absent
        description: FLDOE days absent.
        data_type: numeric
      - name: fl_days_absent_not_disc
        description: FLDOE days absent not disciplinary.
        data_type: numeric
      - name: prior_district
        description: >-
          Prior district — Focus custom field. Stored as an encoded select
          option code (decode deferred).
        data_type: string
      - name: prior_state
        description: >-
          Prior state — Focus custom field. Stored as an encoded select option
          code (decode deferred).
        data_type: string
      - name: prior_country
        description: >-
          Prior country — Focus custom field. Stored as an encoded select option
          code (decode deferred).
        data_type: string
      - name: educational_choice
        description: >-
          Educational choice — Focus custom field. Stored as an encoded select
          option code (decode deferred).
        data_type: string
      - name: student_offender_transfer
        description: >-
          Student offender transfer — Focus custom field. Stored as an encoded
          select option code (decode deferred).
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
`uv run dbt build --select stg_focus__student_enrollment --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS (9591 rows in current
pull, all `id` distinct). All five `custom_*` columns are `STRING`;
`distance_from_school` / `fl_days_*` are `NUMERIC`; the key columns are `INT64`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__student_enrollment.sql src/dbt/focus/models/staging/properties/stg_focus__student_enrollment.yml
git commit -m "feat(dbt): add stg_focus__student_enrollment (#4213)"
```

---

### Task 8: `int_focus__student_enrollment` (intermediate join)

Enriches each enrollment row (the base grain) with its school, grade-level, and
enrollment/withdrawal-code attributes. This is the FIRST model in a new
`intermediate/` layer for the `focus` project — create the directory.

**Grain & join cardinality (profiled against `dagster_kippmiami_dlt_focus`):**

- Base grain: one row per `stg_focus__student_enrollment.id` (9591 rows, all
  `id` distinct). The intermediate preserves this grain exactly — every join is
  many-to-one, so no fan-out.
- `school_id` → `stg_focus__schools.id`: many-to-one. Parent `id` is unique (10
  live rows). Zero orphans against live schools.
- `grade_id` → `stg_focus__school_gradelevels.id`: many-to-one. Parent `id` is
  unique (75 rows). Zero orphans (no NULL `grade_id`).
- `enrollment_code` → `stg_focus__student_enrollment_codes.id`: many-to-one.
  Parent `id` is unique (152 live rows). Zero orphans against live codes
  (`enrollment_code` is non-null on all rows; `drop_code` is null on ~2552 open
  enrollments — left-joined separately and not part of this task's projection to
  keep the grain assertion simple).

All joins are `LEFT JOIN` (preserve every enrollment row even if a parent is
missing in a future pull). Because each parent key is unique, a LEFT JOIN cannot
fan out — the `id` uniqueness test below is the guardrail that proves it.

**Why no contract / no external consumer:** the `focus` project enforces
contracts only under `staging/`, so this intermediate is uncontracted (no
per-column `data_type`). Per `src/dbt/CLAUDE.md`, an intermediate model must
never be read directly by an external tool — a `rpt_*` reporting view must sit
between it and any consumer. This model is internal-only; no `rpt_` is built in
this batch.

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `ref("stg_focus__student_enrollment")`, `ref("stg_focus__schools")`,
  `ref("stg_focus__school_gradelevels")`,
  `ref("stg_focus__student_enrollment_codes")`.
- Produces: model `int_focus__student_enrollment`, grain one row per enrollment
  `id`. Column names produced for downstream: `id`, `syear`, `school_id`,
  `student_id`, `grade_id`, `enrollment_code`, `drop_code`, `calendar_id`,
  `start_date`, `end_date`, `school_title`, `school_state_school_id`,
  `grade_level_title`, `grade_level_short_name`, `enrollment_code_title`,
  `enrollment_code_short_name`, `enrollment_code_type`.

- [ ] **Step 1: Write the model SQL**

ST06 column order — plain refs grouped by source table in join order (one blank
line between groups), then no casts/functions are needed. ST09 — ON-clause
predicates list the earlier-referenced table on the left. This model reads four
tables, so every column is alias-prefixed.

```sql
with
    enrollment as (select * from {{ ref("stg_focus__student_enrollment") }}),

    schools as (select * from {{ ref("stg_focus__schools") }}),

    grade_levels as (select * from {{ ref("stg_focus__school_gradelevels") }}),

    enrollment_codes as (
        select * from {{ ref("stg_focus__student_enrollment_codes") }}
    )

select
    e.id,
    e.syear,
    e.school_id,
    e.student_id,
    e.grade_id,
    e.enrollment_code,
    e.drop_code,
    e.calendar_id,
    e.start_date,
    e.end_date,

    s.title as school_title,
    s.state_school_id as school_state_school_id,

    g.title as grade_level_title,
    g.short_name as grade_level_short_name,

    ec.title as enrollment_code_title,
    ec.short_name as enrollment_code_short_name,
    ec.type as enrollment_code_type,
from enrollment as e
left join schools as s on e.school_id = s.id
left join grade_levels as g on e.grade_id = g.id
left join enrollment_codes as ec on e.enrollment_code = ec.id
```

- [ ] **Step 2: Write the properties YAML**

The uniqueness test is `unique` on `id` (single-column) at `severity: error`. No
`data_type:` keys — the intermediate layer is not contract-enforced.

```yaml
models:
  - name: int_focus__student_enrollment
    description: >-
      Focus student enrollment spans enriched with school, grade-level, and
      enrollment-code attributes. One row per enrollment id; every join is
      many-to-one so the base grain is preserved. Internal-only — a rpt_ view
      must sit between this model and any external consumer.
    columns:
      - name: id
        description: Primary key — Focus student enrollment id.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: syear
        description: Focus school year (start year, e.g. 2025 = 2025-26).
      - name: school_id
        description: Focus school id of the enrollment.
      - name: student_id
        description: Focus student id (local student id).
      - name: grade_id
        description: Focus grade-level id (joins school_gradelevels.id).
      - name: enrollment_code
        description:
          Focus enrollment-code id (joins student_enrollment_codes.id).
      - name: drop_code
        description:
          Focus withdrawal-code id (joins student_enrollment_codes.id).
      - name: calendar_id
        description: Focus attendance calendar id.
      - name: start_date
        description: Enrollment start date.
      - name: end_date
        description: Enrollment withdraw date.
      - name: school_title
        description: Full school name from stg_focus__schools.
      - name: school_state_school_id
        description: State-assigned school id from stg_focus__schools.
      - name: grade_level_title
        description: Full grade-level name from stg_focus__school_gradelevels.
      - name: grade_level_short_name
        description: >-
          Abbreviated grade-level label from stg_focus__school_gradelevels.
      - name: enrollment_code_title
        description: >-
          Full enrollment-code name from stg_focus__student_enrollment_codes.
      - name: enrollment_code_short_name
        description: >-
          Abbreviated enrollment-code label from
          stg_focus__student_enrollment_codes.
      - name: enrollment_code_type
        description: >-
          Enrollment-code classification from
          stg_focus__student_enrollment_codes.
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select int_focus__student_enrollment --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS (9591 rows, no
fan-out). If `unique` fails, a join fanned out — re-profile the offending
parent's `id` uniqueness with the soft-delete filter (`where deleted is null`,
NOT `= 0`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml
git commit -m "feat(dbt): add int_focus__student_enrollment (#4213)"
```

---

## Final verification

- [ ] **Build all eight together** (staging first, then the intermediate that
      depends on four of them — dbt resolves order from `ref()`):

```bash
uv run dbt build --select stg_focus__districts stg_focus__schools stg_focus__school_gradelevels stg_focus__student_enrollment_codes stg_focus__attendance_calendars stg_focus__grad_subject_programs stg_focus__student_enrollment int_focus__student_enrollment --project-dir src/dbt/kippmiami
```

Expected: 8 models build, 16 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook). Run from inside the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__districts.sql \
  src/dbt/focus/models/staging/stg_focus__schools.sql \
  src/dbt/focus/models/staging/stg_focus__school_gradelevels.sql \
  src/dbt/focus/models/staging/stg_focus__student_enrollment_codes.sql \
  src/dbt/focus/models/staging/stg_focus__attendance_calendars.sql \
  src/dbt/focus/models/staging/stg_focus__grad_subject_programs.sql \
  src/dbt/focus/models/staging/stg_focus__student_enrollment.sql \
  src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql \
  src/dbt/focus/models/staging/properties/stg_focus__districts.yml \
  src/dbt/focus/models/staging/properties/stg_focus__schools.yml \
  src/dbt/focus/models/staging/properties/stg_focus__school_gradelevels.yml \
  src/dbt/focus/models/staging/properties/stg_focus__student_enrollment_codes.yml \
  src/dbt/focus/models/staging/properties/stg_focus__attendance_calendars.yml \
  src/dbt/focus/models/staging/properties/stg_focus__grad_subject_programs.yml \
  src/dbt/focus/models/staging/properties/stg_focus__student_enrollment.yml \
  src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml
```

## Out of scope (other plans / issues)

- The **unpopulated** `custom_*` long-tail on `student_enrollment` (15 columns)
  and `schools` (48 columns) — no non-null values in the current pull, so not
  projected.
- Decoding `select` / `multiple` custom values from their stored Focus option
  codes to human-readable labels (e.g. `schools.school_level`,
  `schools.school_type`, `schools.technical_center`) — deferred follow-up; the
  values land here as raw codes.
- The raw `custom_fields` JSON blobs.
- `rpt_*` reporting views over `int_focus__student_enrollment` and any kipptaf
  `stg_kippmiami__focus__*` wrappers — deferred to the kipptaf-integration plan
  (the kipptaf source resolves to prod for `target=staging` CI, so district
  staging must land in prod first).

## Self-review checklist (run before handing off)

1. **Spec coverage:** all seven Batch B tables have a staging task (Tasks 1–7)
   and the intermediate model is Task 8. The two WIDE tables (`schools`,
   `student_enrollment`) each carry the inline populated-custom block sourced
   from their map file. ✓
2. **Placeholder scan:** every task carries complete SQL + complete YAML + exact
   build command. No TBD/TODO/"similar to". ✓
3. **Type consistency:** each staging YAML `data_type` matches the warehouse
   type. The `schools` custom block's `INT64` trio (`school_level`,
   `school_type`, `technical_center`) vs `STRING` quintet is called out; the
   `student_enrollment` customs are all `STRING`; the `school_gradelevels`
   `min_syear`/`max_syear` NUMERIC-vs-INT difference is flagged. ✓
4. **PK correctness:** `id` for districts/schools/school_gradelevels/
   student_enrollment_codes/grad_subject_programs/student_enrollment;
   `calendar_id` for attendance_calendars (no `id` column on that table). ✓
5. **Soft-delete:** `where deleted is null` on `schools` and
   `student_enrollment_codes` (NULL = live; `= 0` returns zero rows). The other
   five tables have no `deleted` column. ✓
6. **Populated customs:** every map row is projected `<raw> as <slug>` (or plain
   `custom_N` where slug = raw name, avoiding an AL09 self-alias), placed after
   the core and before any cast block (ST06). No map column is duplicated under
   another alias; no off-map custom is added. Each YAML entry's `name` = slug,
   `data_type` = mapped bq_type, `description` = title when present else the
   generic-slot fallback. Values left encoded; descriptions note codes are not
   decoded. ✓
7. **Intermediate rules:** uniqueness test present (`unique` on `id`, error
   severity); no contract/`data_type` (layer not enforced); no external consumer
   (rpt\_ buffer noted as out of scope). Join cardinality documented and all
   many-to-one. ✓
