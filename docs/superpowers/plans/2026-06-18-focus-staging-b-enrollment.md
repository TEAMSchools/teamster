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
column. A new `intermediate/` layer adds `int_focus__student_enrollment`, a
many-to-one enrichment of enrollment rows with school, grade-level, and
enrollment-code attributes. Models build inside the consuming district project
(`kippmiami`), which sets `focus_schema` and imports the `focus` package.

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
- **Soft-delete filter (CORRECTED — see Open Questions):** In this Miami Focus
  dataset, the `deleted` column on `schools` and `student_enrollment_codes` is
  `NULL` for live rows and `1` for deleted rows — NOT `0` for live. A
  `where deleted = 0` filter (as the Phase B index states) returns ZERO rows.
  Use `where deleted is null` and OMIT the `deleted` column from the projection.
  The other five tables in this batch have no `deleted` column. (`districts`,
  `school_gradelevels`, `attendance_calendars`, `grad_subject_programs` carry an
  `active` / `rollover` / `default_calendar` STRING flag, NOT a delete flag —
  keep those raw.)
- WIDE tables (`student_enrollment` 62 cols, `schools` 85 cols): carry the
  curated core set only — the import-layout-mapped FLDOE columns plus keys,
  dates, names, and audit timestamps. The `custom_*` long-tail is OUT OF SCOPE
  for this batch — it is handled by the separate Batch H custom-field unpivot
  model (entity `custom_NNN` columns → long key/value joined to the
  `custom_fields` metadata crosswalk). Specific meaningful `custom_NNN` columns
  named in the import-layout mapping ARE included by name (e.g.
  `schools.custom_327` = school number, `student_enrollment.custom_1` = prior
  district).
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
opaque STRING pass-throughs; the structured unpivot is Batch H.

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
          Raw Focus custom-fields JSON blob; structured values are exposed by
          the Batch H custom-field unpivot, not here.
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

### Task 2: `stg_focus__schools` (WIDE — curated)

`schools` has 85 columns (after excluding `_dlt_*`), 50+ of them `custom_*`
fields. Curate to: the natural/foreign keys (`id`, `district_id`,
`state_school_id`, `erp_facility_id`), the school-year bounds (`min_syear` /
`max_syear`), `title`, geo (`latitude` / `longitude`), `sort_order`, the
FLDOE-mapped `custom_NNN` columns from the import layout (school number,
address, principal, school level/type, federal id, etc.), and audit timestamps +
`uuid`. **Soft-delete:** `deleted` is `NULL` for live rows here (NOT `0`) —
filter `where deleted is null` and OMIT `deleted`. The full `custom_*` long-tail
(and the `custom_fields` JSON blob) is OUT OF SCOPE — Batch H. `custom_1` /
`custom_3` / `area_code` / `custom_100000005` / `custom_l913` /
`custom_300000005` are unmapped `NUMERIC` long-tail and dropped.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__schools.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__schools.yml`

**Interfaces:**

- Consumes: `source("focus", "schools")`
- Produces: model `stg_focus__schools`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

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
    custom_327,
    custom_200000319,
    custom_200000320,
    custom_200000321,
    custom_200000322,
    custom_200000323,
    custom_200000324,
    custom_200000325,
    custom_100000004,
    custom_100000001,
    custom_100000002,
    custom_100000003,
    custom_50000000,
    custom_50000001,
    custom_50000002,
    custom_200000326,
    custom_201200001,
    custom_2012197245,
    custom_201300001,
    custom_200000200,
    custom_200000300,
    custom_200000301,
    custom_100000007,
    custom_200000302,
    virtual,
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
      excluded). Carries the curated core plus the FLDOE import-layout fields
      (school number, address, principal, level/type, federal id). The full
      Focus custom-field long-tail is exposed by the Batch H custom-field
      unpivot, not here.
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
      - name: custom_327
        description: FLDOE school number (import field SCH_ID).
        data_type: string
      - name: custom_200000319
        description: School street address (import field ADDRESS_1).
        data_type: string
      - name: custom_200000320
        description: School city (import field CITY).
        data_type: string
      - name: custom_200000321
        description: School state (import field STATE).
        data_type: string
      - name: custom_200000322
        description: School ZIP code (import field ZIP).
        data_type: string
      - name: custom_200000323
        description: School phone number (import field PH_NUM).
        data_type: string
      - name: custom_200000324
        description: Principal name (import field PRINCIPAL_NAME).
        data_type: string
      - name: custom_200000325
        description: School web address (import field WEB_ADDRESS).
        data_type: string
      - name: custom_100000004
        description: School level code (import field SCH_LVL).
        data_type: int
      - name: custom_100000001
        description: District number (import field DISTRICT_NUM).
        data_type: string
      - name: custom_100000002
        description: WDIS-only school flag (import field WDIS_ONLY_SCH).
        data_type: string
      - name: custom_100000003
        description: McKay school flag (import field MCKAY_SCH).
        data_type: string
      - name: custom_50000000
        description: IB program code (import field IB).
        data_type: int
      - name: custom_50000001
        description: AIC program code (import field AIC).
        data_type: int
      - name: custom_50000002
        description: Technical center code (import field TECH_CENTER).
        data_type: int
      - name: custom_200000326
        description: School type code (import field SCH_TYPE).
        data_type: int
      - name: custom_201200001
        description: PERT site code (import field PERT_SITE_CD).
        data_type: string
      - name: custom_2012197245
        description: Summer school flag (import field SUMMER_SCH).
        data_type: string
      - name: custom_201300001
        description: >-
          Community Eligibility Provision (CEP) school flag (import field
          CEP_SCH).
        data_type: string
      - name: custom_200000200
        description: >-
          Exclude-from-state-reporting flag (import field EXC_STATE_REPORT).
        data_type: string
      - name: custom_200000300
        description: Federal school identifier (import field FED_SCH_ID).
        data_type: string
      - name: custom_200000301
        description: Double-session school flag (import field DBL_SESSION_SCHL).
        data_type: string
      - name: custom_100000007
        description: Total scheduled minutes (import field TOTAL_SCHED_MINS).
        data_type: numeric
      - name: custom_200000302
        description: Title 1 flag (import field TITLE_1).
        data_type: string
      - name: virtual
        description: Y/N — whether the school is virtual.
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
only live rows (10 in the current Miami pull). Watch the `int` vs `string`
custom-field splits above — `custom_100000004` / `custom_50000000` /
`custom_50000001` / `custom_50000002` / `custom_200000326` are `INT64` in the
warehouse; the rest of the mapped customs are `STRING`. Match the YAML exactly
or the contract fails.

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

### Task 7: `stg_focus__student_enrollment` (WIDE — curated)

`student_enrollment` has 62 columns (after excluding `_dlt_*`). Curate to: the
keys (`id`, `school_id`, `student_id`, `grade_id`, `enrollment_code`,
`drop_code`, `calendar_id`, `graduation_requirement_program`, `next_school`,
`program_id`, `next_year_program_id`, `team_id`), the dates (`start_date` /
`end_date`), the FLDOE state-reporting day counts (`fl_days_present` /
`fl_days_absent` / `fl_days_absent_not_disc`), the mapped `custom_NNN` FLDOE
fields (prior district/state/country, ed choice, came-from / moved-to, grade
promotion, etc.), the non-custom mapped fields (`include_in_class_rank`,
`next_grade`, `imported`), plus audit timestamps + `uuid`. **No soft-delete
column** on this table. The unmapped `custom_NNN` long-tail and free-text
`notes` are OUT OF SCOPE (Batch H / not curated): `custom_10`,
`custom_13`–`custom_15`, `custom_18`–`custom_20` are dropped.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__student_enrollment.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `source("focus", "student_enrollment")`
- Produces: model `stg_focus__student_enrollment`, grain one row per `id`.
  Consumed by `int_focus__student_enrollment` (Task 8) as the base table.

- [ ] **Step 1: Write the model SQL**

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
    custom_1,
    custom_2,
    custom_3,
    custom_4,
    custom_5,
    custom_6,
    custom_7,
    custom_8,
    custom_9,
    custom_11,
    custom_12,
    custom_16,
    custom_17,
    fl_days_present,
    fl_days_absent,
    fl_days_absent_not_disc,
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
      plus the FLDOE import-layout fields (prior district/state/country,
      educational choice, came-from / moved-to, grade promotion, day counts).
      The uncurated Focus custom-field long-tail is exposed by the Batch H
      custom-field unpivot, not here.
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
        description: Enrollment start date (import field START_DATE).
        data_type: date
      - name: end_date
        description: Enrollment withdraw date (import field END_DATE).
        data_type: date
      - name: include_in_class_rank
        description: >-
          Y/N — whether the enrollment is included in class rank (import field
          INCLUDE_IN_CLASS_RANK).
        data_type: string
      - name: distance_from_school
        description: Distance from the student's home to the school.
        data_type: numeric
      - name: next_grade
        description: Next grade level (import field NEXT_GRADE).
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
      - name: custom_1
        description: Prior district (import field PRIOR_DIST).
        data_type: string
      - name: custom_2
        description: Prior state (import field PRIOR_STATE).
        data_type: string
      - name: custom_3
        description: Prior country (import field PRIOR_COUNTRY).
        data_type: string
      - name: custom_4
        description: Educational choice (import field ED_CHOICE).
        data_type: string
      - name: custom_5
        description: Disaster-affected student (import field STDT_DIS_AFFECT).
        data_type: string
      - name: custom_6
        description:
          Student offender transfer (import field OFFENDER_TRANSFER_STDT).
        data_type: string
      - name: custom_7
        description: Came from (import field CAME_FROM).
        data_type: string
      - name: custom_8
        description: Moved to (import field MOVED_TO).
        data_type: string
      - name: custom_9
        description: Second school (import field SEC_SCH).
        data_type: string
      - name: custom_11
        description: Grade promotion status (import field GRDE_PROM_ST).
        data_type: string
      - name: custom_12
        description: Good cause exemption (import field GOOD_CAUSE_EXEMPT).
        data_type: string
      - name: custom_16
        description: District out-of-district (import field DISTRICT_OOD).
        data_type: string
      - name: custom_17
        description: School out-of-district (import field SCH_OOD).
        data_type: string
      - name: fl_days_present
        description: FLDOE days present (import field FL_DAYS_PRESENT).
        data_type: numeric
      - name: fl_days_absent
        description: FLDOE days absent (import field FL_DAYS_ABSENT).
        data_type: numeric
      - name: fl_days_absent_not_disc
        description: FLDOE days absent not disciplinary.
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
`uv run dbt build --select stg_focus__student_enrollment --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS (9591 rows in current
pull, all `id` distinct). All `custom_*` columns above are `STRING`;
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
predicates list the earlier-referenced table on the left. No alias prefixes are
needed only when a single table is read; this model reads four tables, so every
column is alias-prefixed.

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
parent's `id` uniqueness with the corrected soft-delete filter
(`where deleted is null`, NOT `= 0`).

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

- The `custom_*` long-tail on `student_enrollment` and `schools` (and the
  `custom_fields` JSON blobs) — Batch H custom-field unpivot.
- `rpt_*` reporting views over `int_focus__student_enrollment` and any kipptaf
  `stg_kippmiami__focus__*` wrappers — deferred to the kipptaf-integration plan
  (the kipptaf source resolves to prod for `target=staging` CI, so district
  staging must land in prod first).

## Self-review checklist (run before handing off)

1. **Spec coverage:** all seven Batch B tables have a staging task (Tasks 1–7)
   and the intermediate model is Task 8. ✓
2. **Placeholder scan:** every task carries complete SQL + complete YAML + exact
   build command. No TBD/TODO/"similar to". ✓
3. **Type consistency:** each staging YAML `data_type` matches the warehouse
   type from `INFORMATION_SCHEMA.COLUMNS` (int/string/numeric/date/timestamp/
   boolean). The `schools` custom-field int-vs-string split and the
   `school_gradelevels` `min_syear`/`max_syear` NUMERIC-vs-INT difference are
   called out at the build step. ✓
4. **PK correctness:** `id` for districts/schools/school_gradelevels/
   student_enrollment_codes/grad_subject_programs/student_enrollment;
   `calendar_id` for attendance_calendars (no `id` column on that table). ✓
5. **Soft-delete:** CORRECTED to `where deleted is null` on `schools` and
   `student_enrollment_codes` (the index's `= 0` returns zero rows — see Open
   Questions). The other five tables have no `deleted` column. ✓
6. **Intermediate rules:** uniqueness test present (`unique` on `id`, error
   severity); no contract/`data_type` (layer not enforced); no external consumer
   (rpt\_ buffer noted as out of scope). Join cardinality documented and all
   many-to-one. ✓
