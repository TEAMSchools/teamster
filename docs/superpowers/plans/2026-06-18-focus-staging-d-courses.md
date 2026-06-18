# Focus Staging — Courses & Scheduling (Batch D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the eight
populated Focus courses-and-scheduling tables (`courses`, `course_periods`,
`course_subjects`, `course_weights`, `master_courses`, `course_code_directory`,
`co_teacher_days`, `resources`) in the `focus` source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
uniqueness + `not_null` test on each table's primary key, and a `description:`
on the model and every column. The three wide tables (`courses` 57 cols,
`master_courses` 109 cols, `course_periods` 289 cols) are curated to the
FLDOE-import-mapped core plus keys/dates/names; their `custom_*` /
`custom_field_*` / per-co-teacher long tail is intentionally excluded and
handled by the separate Batch H custom-field unpivot. Models build inside the
consuming district project (`kippmiami`), which sets `focus_schema` and imports
the `focus` package.

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
- Exclude dlt bookkeeping columns (`_dlt_*`) and the audit-quad
  (`created_by_class`, `created_by_id`, `updated_by_class`, `updated_by_id`)
  from every model. Keep `created_at` / `updated_at` / `uuid`.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`).
- **No soft-delete in this batch.** None of these eight tables has a `deleted`
  column, so there is NO `where deleted = 0` filter. `course_periods` carries an
  `active STRING` flag and `master_courses` a `status INT64`; their semantics
  are unconfirmed, so keep them as raw projected columns — do NOT filter on
  them. Add a filter only in a later intermediate layer if a consumer needs it.
- **Wide-table curation:** `courses`, `master_courses`, and `course_periods`
  carry a large `custom_*` / `custom_field_*` / per-co-teacher (`co_teacher*_*`)
  long tail that is OUT OF SCOPE here — it is handled by the Batch H
  custom-field unpivot. Each wide staging model projects only the curated core:
  the FLDOE-import-mapped columns (named columns + specifically-mapped
  `custom_NNN`) plus primary/foreign keys, dates, names, and
  `uuid`/`created_at`/`updated_at`. The exact projected column set is enumerated
  per task below; do not add the long-tail columns.
- Focus columns are already `snake_case`. No BigQuery reserved-word column names
  appear in these eight tables, so no backtick-quoting / `quote: true` is
  needed. Y/N-style flags and checkbox fields stay raw `STRING` (convert to
  booleans in an intermediate layer later if a consumer needs it).
- Build/test context is the **kippmiami** project, not `focus` standalone.
- BigQuery type-synonym note for contract YAML: warehouse `INT64` → YAML `int`;
  `STRING` → `string`; `NUMERIC` → `numeric`; `DATE` → `date`; `TIMESTAMP` →
  `timestamp`. `numeric` and `float64` are NOT interchangeable.

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__course_subjects`

Narrow table (17 columns). PK is `subject_id` (verified unique: 1262 / 1262
rows). Excludes the audit-quad; `custom_1`–`custom_3` are FLDOE-mapped
(`VOC_PRGM_NUM`, `TOTAL_HRS_PRGM`, plus one unmapped) so they stay.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__course_subjects.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__course_subjects.yml`

**Interfaces:**

- Consumes: `source("focus", "course_subjects")`
- Produces: model `stg_focus__course_subjects`, grain one row per `subject_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    subject_id,
    syear,
    school_id,
    rollover_id,
    title,
    short_name,
    custom_1,
    custom_2,
    custom_3,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "course_subjects") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__course_subjects
    description: >-
      Focus course subjects — one row per subject, scoped by school year and
      school. Lookup that groups courses under a subject area.
    columns:
      - name: subject_id
        description: Primary key — Focus course subject id.
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
        description: Focus school number the subject belongs to.
        data_type: int
      - name: rollover_id
        description: Source subject id this rolled over from.
        data_type: int
      - name: title
        description: Full subject title.
        data_type: string
      - name: short_name
        description: Abbreviated subject label.
        data_type: string
      - name: custom_1
        description: Vocational program number (FLDOE VOC_PRGM_NUM).
        data_type: string
      - name: custom_2
        description: Total hours for the program (FLDOE TOTAL_HRS_PRGM).
        data_type: string
      - name: custom_3
        description: Focus custom subject attribute slot 3.
        data_type: string
      - name: imported
        description: Y/N — whether the row originated from an import.
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
`uv run dbt build --select stg_focus__course_subjects --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `subject_id` PASS. A
contract mismatch here means a `data_type` in the YAML disagrees with the
warehouse — fix the YAML to match `INFORMATION_SCHEMA.COLUMNS`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__course_subjects.sql src/dbt/focus/models/staging/properties/stg_focus__course_subjects.yml
git commit -m "feat(dbt): add stg_focus__course_subjects (#4213)"
```

---

### Task 2: `stg_focus__course_weights`

Narrow table (29 columns). PK is `id` (verified unique: 17221 / 17221 rows).
Excludes the audit-quad. Keeps the `does_gpa_*` / `cw_checkbox_setting_*` flag
columns (these are part of the core weight definition, not the unpivot long
tail).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__course_weights.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__course_weights.yml`

**Interfaces:**

- Consumes: `source("focus", "course_weights")`
- Produces: model `stg_focus__course_weights`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    course_id,
    course_weight,
    gpa_multiplier,
    rollover_id,
    year_fraction,
    credits,
    student_requestable,
    student_scheduleable,
    cw_checkbox_setting_1,
    cw_checkbox_setting_2,
    cw_checkbox_setting_3,
    cw_checkbox_setting_4,
    cw_checkbox_setting_5,
    does_gpa_1,
    does_gpa_2,
    does_gpa_3,
    does_gpa_4,
    does_gpa_5,
    teacher_approve,
    imported,
    created_at,
    updated_at,
from {{ source("focus", "course_weights") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__course_weights
    description: >-
      Focus course weights — one row per weighting of a course, holding GPA
      multiplier, credits, and the per-course-history-term scheduling flags.
    columns:
      - name: id
        description: Primary key — Focus course weight id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: school_id
        description: Focus school number.
        data_type: int
      - name: course_id
        description: Focus course id this weight applies to.
        data_type: int
      - name: course_weight
        description: Course weight label / course-history-term identifier.
        data_type: string
      - name: gpa_multiplier
        description: GPA multiplier applied for this weight.
        data_type: numeric
      - name: rollover_id
        description: Source course weight id this rolled over from.
        data_type: int
      - name: year_fraction
        description: Fraction of the school year this weight represents.
        data_type: numeric
      - name: credits
        description: Credits per course-history term (FLDOE CREDITS).
        data_type: numeric
      - name: student_requestable
        description: Y/N — whether students may request this weight.
        data_type: string
      - name: student_scheduleable
        description: Y/N — whether this weight is student-schedulable.
        data_type: string
      - name: cw_checkbox_setting_1
        description: Course-weight checkbox setting slot 1.
        data_type: string
      - name: cw_checkbox_setting_2
        description: Course-weight checkbox setting slot 2.
        data_type: string
      - name: cw_checkbox_setting_3
        description: Course-weight checkbox setting slot 3.
        data_type: string
      - name: cw_checkbox_setting_4
        description: Course-weight checkbox setting slot 4.
        data_type: string
      - name: cw_checkbox_setting_5
        description: Course-weight checkbox setting slot 5.
        data_type: string
      - name: does_gpa_1
        description: Y/N — whether this weight counts toward GPA scheme 1.
        data_type: string
      - name: does_gpa_2
        description: Y/N — whether this weight counts toward GPA scheme 2.
        data_type: string
      - name: does_gpa_3
        description: Y/N — whether this weight counts toward GPA scheme 3.
        data_type: string
      - name: does_gpa_4
        description: Y/N — whether this weight counts toward GPA scheme 4.
        data_type: string
      - name: does_gpa_5
        description: Y/N — whether this weight counts toward GPA scheme 5.
        data_type: string
      - name: teacher_approve
        description: Y/N — whether teacher approval is required for this weight.
        data_type: string
      - name: imported
        description: Y/N — whether the row originated from an import.
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
`uv run dbt build --select stg_focus__course_weights --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__course_weights.sql src/dbt/focus/models/staging/properties/stg_focus__course_weights.yml
git commit -m "feat(dbt): add stg_focus__course_weights (#4213)"
```

---

### Task 3: `stg_focus__course_code_directory`

Narrow table (35 columns). PK is `id` (standard `id` surrogate). Excludes the
audit-quad; keeps all FLDOE course-code directory descriptor columns.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__course_code_directory.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__course_code_directory.yml`

**Interfaces:**

- Consumes: `source("focus", "course_code_directory")`
- Produces: model `stg_focus__course_code_directory`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    course_number,
    course_symbol,
    voc_gradelevels,
    abrev_course_title,
    course_title,
    course_year,
    cert_levels,
    subject_area,
    max_credit,
    subject_code,
    subject_subfield,
    sort_level,
    required_course,
    new_course_number,
    abrev_course_title2,
    new_course_title,
    abrev_title_symbol,
    title_symbol,
    new_short_symbol,
    new_title_f35_symbol,
    new_title_l35_symbol,
    course_level,
    core_course,
    highly_qualified,
    course_length,
    eoc_indicator,
    course_indicator,
    created_at,
    updated_at,
from {{ source("focus", "course_code_directory") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__course_code_directory
    description: >-
      Focus course code directory — one row per state course-code entry. The
      FLDOE course-code crosswalk mapping legacy and current course numbers,
      titles, symbols, and reporting indicators.
    columns:
      - name: id
        description: Primary key — Focus course code directory id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: course_number
        description: State course number.
        data_type: string
      - name: course_symbol
        description: Course symbol code.
        data_type: string
      - name: voc_gradelevels
        description: Vocational grade levels the course applies to.
        data_type: string
      - name: abrev_course_title
        description: Abbreviated course title.
        data_type: string
      - name: course_title
        description: Full course title.
        data_type: string
      - name: course_year
        description: Effective course year.
        data_type: string
      - name: cert_levels
        description: Certification levels associated with the course.
        data_type: string
      - name: subject_area
        description: Subject area classification.
        data_type: string
      - name: max_credit
        description: Maximum credit allowed for the course.
        data_type: string
      - name: subject_code
        description: Subject code.
        data_type: string
      - name: subject_subfield
        description: Subject subfield code.
        data_type: string
      - name: sort_level
        description: Sort level within the directory.
        data_type: string
      - name: required_course
        description: Y/N — whether the course is required.
        data_type: string
      - name: new_course_number
        description: Replacement (new) course number.
        data_type: string
      - name: abrev_course_title2
        description: Secondary abbreviated course title.
        data_type: string
      - name: new_course_title
        description: Replacement (new) course title.
        data_type: string
      - name: abrev_title_symbol
        description: Abbreviated title symbol.
        data_type: string
      - name: title_symbol
        description: Title symbol.
        data_type: string
      - name: new_short_symbol
        description: Replacement (new) short symbol.
        data_type: string
      - name: new_title_f35_symbol
        description: Replacement title first-35-character symbol.
        data_type: string
      - name: new_title_l35_symbol
        description: Replacement title last-35-character symbol.
        data_type: string
      - name: course_level
        description: Course level classification.
        data_type: string
      - name: core_course
        description: Y/N — whether the course is a core course.
        data_type: string
      - name: highly_qualified
        description:
          Y/N — whether the course requires a highly-qualified teacher.
        data_type: string
      - name: course_length
        description: Course length classification.
        data_type: string
      - name: eoc_indicator
        description: End-of-course (EOC) reporting indicator.
        data_type: string
      - name: course_indicator
        description: General course reporting indicator.
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
`uv run dbt build --select stg_focus__course_code_directory --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__course_code_directory.sql src/dbt/focus/models/staging/properties/stg_focus__course_code_directory.yml
git commit -m "feat(dbt): add stg_focus__course_code_directory (#4213)"
```

---

### Task 4: `stg_focus__co_teacher_days`

Narrow table (17 columns). PK is `id` (verified unique: 30 / 30 rows). Excludes
the audit-quad. The single-letter columns (`f`, `h`, `m`, `s`, `t`, `u`, `w`)
are per-rotation-day flags keyed by weekday initial — kept as-is.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__co_teacher_days.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__co_teacher_days.yml`

**Interfaces:**

- Consumes: `source("focus", "co_teacher_days")`
- Produces: model `stg_focus__co_teacher_days`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    course_period_id,
    teacher_id,
    f,
    h,
    m,
    s,
    t,
    u,
    w,
    imported,
    created_at,
    updated_at,
from {{ source("focus", "co_teacher_days") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__co_teacher_days
    description: >-
      Focus co-teacher days — one row per co-teacher assignment to a course
      period, with per-rotation-day flags keyed by weekday initial.
    columns:
      - name: id
        description: Primary key — Focus co-teacher days id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: course_period_id
        description: Focus course-period (section) id the co-teacher serves.
        data_type: int
      - name: teacher_id
        description: Focus staff id of the co-teacher.
        data_type: int
      - name: f
        description: Friday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: h
        description: Thursday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: m
        description: Monday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: s
        description: Saturday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: t
        description: Tuesday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: u
        description: Sunday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: w
        description: Wednesday rotation-day flag for the co-teacher assignment.
        data_type: numeric
      - name: imported
        description: Y/N — whether the row originated from an import.
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
`uv run dbt build --select stg_focus__co_teacher_days --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__co_teacher_days.sql src/dbt/focus/models/staging/properties/stg_focus__co_teacher_days.yml
git commit -m "feat(dbt): add stg_focus__co_teacher_days (#4213)"
```

---

### Task 5: `stg_focus__resources`

Narrow table (21 columns). PK is `id` (standard `id` surrogate). Excludes the
audit-quad. Models rooms/resources scheduled against course periods.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__resources.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__resources.yml`

**Interfaces:**

- Consumes: `source("focus", "resources")`
- Produces: model `stg_focus__resources`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    school_id,
    category_id,
    title,
    short_name,
    type,
    comments,
    seats,
    imported,
    display_room,
    room_description,
    square_footage,
    max_syear,
    min_syear,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "resources") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__resources
    description: >-
      Focus resources — one row per schedulable resource (typically a room),
      scoped to a school and an active school-year range.
    columns:
      - name: id
        description: Primary key — Focus resource id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: school_id
        description: Focus school number the resource belongs to.
        data_type: int
      - name: category_id
        description: Focus resource category id.
        data_type: int
      - name: title
        description: Full resource title.
        data_type: string
      - name: short_name
        description: Abbreviated resource label.
        data_type: string
      - name: type
        description: Y/N — whether the resource is a room (FLDOE TYPE).
        data_type: string
      - name: comments
        description: Free-text comments on the resource.
        data_type: string
      - name: seats
        description: Maximum seats in the room (FLDOE SEATS).
        data_type: numeric
      - name: imported
        description: Y/N — whether the row originated from an import.
        data_type: string
      - name: display_room
        description: Display label for the room.
        data_type: string
      - name: room_description
        description: Room description (FLDOE ROOM_DESCRIPTION).
        data_type: string
      - name: square_footage
        description: Square footage of the room (FLDOE SQUARE_FOOTAGE).
        data_type: int
      - name: max_syear
        description: Last school year the resource is active.
        data_type: int
      - name: min_syear
        description: First school year the resource is active (FLDOE MIN_SYEAR).
        data_type: int
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
`uv run dbt build --select stg_focus__resources --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__resources.sql src/dbt/focus/models/staging/properties/stg_focus__resources.yml
git commit -m "feat(dbt): add stg_focus__resources (#4213)"
```

---

### Task 6: `stg_focus__courses` (WIDE — curated)

`courses` has 57 columns. The `custom_1`–`custom_12` long tail is OUT OF SCOPE
(Batch H unpivot), EXCEPT the two FLDOE-mapped slots kept by name: `custom_2`
(WDIS OCP HOURS) and `custom_10` (CAPE). Curate to the import-mapped core plus
the course/subject/grad keys, dates, names, length/occurrences, and
`uuid`/`created_at`/`updated_at`. PK is `course_id` (verified unique: 16904 /
16904 rows).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__courses.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__courses.yml`

**Interfaces:**

- Consumes: `source("focus", "courses")`
- Produces: model `stg_focus__courses`, grain one row per `course_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    course_id,
    syear,
    subject_id,
    school_id,
    district_id,
    title,
    short_name,
    alternate_title,
    rollover_id,
    grad_subject_id,
    grad_subject_id2,
    grad_subject_id3,
    mp,
    grade_level,
    prerequisites,
    prerequisites_2,
    prerequisites_3,
    need_approval,
    teacher_requestable,
    requests_subject,
    priority,
    description,
    length,
    occurrences,
    credit_hours,
    course_hours,
    allow_repeat,
    homeroom,
    edfi_course_level_characteristic,
    iet_program_number,
    custom_2,
    custom_10,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "courses") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__courses
    description: >-
      Focus courses — one row per course definition, scoped by school year and
      school. Curated to the FLDOE-import-mapped core plus course/subject keys,
      titles, prerequisites, and scheduling attributes. The custom-field long
      tail is excluded and handled by the Batch H custom-field unpivot.
    columns:
      - name: course_id
        description: Primary key — Focus course id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: syear
        description: Focus school year (start year, FLDOE SYEAR).
        data_type: int
      - name: subject_id
        description: Focus course subject id (FLDOE SUBJECT_ID).
        data_type: int
      - name: school_id
        description: Focus school number (FLDOE SCHOOL_ID).
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full course title (FLDOE TITLE).
        data_type: string
      - name: short_name
        description: Course number / abbreviated label (FLDOE SHORT_NAME).
        data_type: string
      - name: alternate_title
        description: Alternate course title.
        data_type: string
      - name: rollover_id
        description: Source course id this rolled over from.
        data_type: int
      - name: grad_subject_id
        description: Graduation requirement subject id (FLDOE GRAD_SUBJECT_ID).
        data_type: int
      - name: grad_subject_id2
        description: Second graduation requirement subject id.
        data_type: int
      - name: grad_subject_id3
        description: Third graduation requirement subject id.
        data_type: int
      - name: mp
        description: Marking period scope for the course (FLDOE MP).
        data_type: string
      - name: grade_level
        description: Grade level the course is offered at.
        data_type: string
      - name: prerequisites
        description: Course prerequisite expression.
        data_type: string
      - name: prerequisites_2
        description: Second course prerequisite expression.
        data_type: string
      - name: prerequisites_3
        description: Third course prerequisite expression.
        data_type: string
      - name: need_approval
        description: Y/N — whether enrollment in the course needs approval.
        data_type: string
      - name: teacher_requestable
        description: Y/N — whether teachers may request the course.
        data_type: string
      - name: requests_subject
        description: Y/N — whether the course participates in subject requests.
        data_type: string
      - name: priority
        description: Scheduling priority for the course.
        data_type: string
      - name: description
        description: Free-text course description.
        data_type: string
      - name: length
        description: Course length value.
        data_type: numeric
      - name: occurrences
        description: Number of occurrences for the course.
        data_type: numeric
      - name: credit_hours
        description: Credit hours awarded by the course.
        data_type: numeric
      - name: course_hours
        description: Instructional course hours.
        data_type: numeric
      - name: allow_repeat
        description: Y/N — whether the course may be repeated.
        data_type: string
      - name: homeroom
        description: Y/N — whether the course is a homeroom.
        data_type: string
      - name: edfi_course_level_characteristic
        description: Ed-Fi course-level characteristic code.
        data_type: string
      - name: iet_program_number
        description: IET program number associated with the course.
        data_type: string
      - name: custom_2
        description: WDIS OCP hours (FLDOE WDIS_OCP_HRS).
        data_type: string
      - name: custom_10
        description: CAPE indicator (FLDOE CAPE).
        data_type: string
      - name: imported
        description: Y/N — whether the row originated from an import.
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
`uv run dbt build --select stg_focus__courses --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `course_id` PASS. If a contract
mismatch fires, confirm each projected column's YAML `data_type` matches the
warehouse type (`length`/`occurrences` are `numeric`, not `int`/`float64`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__courses.sql src/dbt/focus/models/staging/properties/stg_focus__courses.yml
git commit -m "feat(dbt): add stg_focus__courses (#4213)"
```

---

### Task 7: `stg_focus__master_courses` (WIDE — curated)

`master_courses` has 109 columns. The `custom_field_1`–`custom_field_20` long
tail is OUT OF SCOPE (Batch H unpivot) — none of the FLDOE-mapped
`custom_field_*` slots are kept by name here; the mapped descriptive fields
(course level, GPA, grading scale, credits, dates, etc.) are all native columns.
Curate to the import-mapped core plus the course/subject keys, titles, dates,
grading, and `uuid`/`created_at`/`updated_at`. PK is `course_id` (verified
unique: 71283 / 71283 rows).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__master_courses.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__master_courses.yml`

**Interfaces:**

- Consumes: `source("focus", "master_courses")`
- Produces: model `stg_focus__master_courses`, grain one row per `course_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    course_id,
    subject_id,
    syear,
    district_id,
    rollover_id,
    short_name,
    title,
    long_title,
    transcript_title,
    start_date,
    end_date,
    date_added,
    last_modified_date,
    grad_subject_area,
    grad_subject_area2,
    grad_subject_area3,
    subject_area,
    edfi_core_subject,
    grading_scale,
    standards_grading_scale,
    grade_posting_scheme,
    course_history_term,
    course_level,
    course_length,
    affects_gpa,
    credits,
    total_credit,
    credit_hours,
    course_hours,
    fee,
    low_grade,
    high_grade,
    gender_restriction,
    status,
    ib,
    ap,
    ell,
    certification_requirements,
    course_description,
    allow_repeat,
    homeroom,
    edfi_course_level_characteristic,
    iet_program_number,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "master_courses") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__master_courses
    description: >-
      Focus master courses — one row per master course template, scoped by
      school year. Curated to the FLDOE-import-mapped core plus course/subject
      keys, titles, term dates, grading scheme, and credit attributes. The
      custom-field long tail is excluded and handled by the Batch H unpivot.
    columns:
      - name: course_id
        description: Primary key — Focus master course id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: subject_id
        description: Focus course subject id.
        data_type: int
      - name: syear
        description: Focus school year (start year, FLDOE SYEAR).
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: rollover_id
        description: Source master course id this rolled over from.
        data_type: int
      - name: short_name
        description: Course number / abbreviated label (FLDOE SHORT_NAME).
        data_type: string
      - name: title
        description: Full course title (FLDOE TITLE).
        data_type: string
      - name: long_title
        description: Long course title (FLDOE LONG_TITLE).
        data_type: string
      - name: transcript_title
        description: Title used on transcripts.
        data_type: string
      - name: start_date
        description: Course start date (FLDOE START_DATE).
        data_type: date
      - name: end_date
        description: Course end date (FLDOE END_DATE).
        data_type: date
      - name: date_added
        description: Date the master course was added (FLDOE DATE_ADDED).
        data_type: date
      - name: last_modified_date
        description: Date the master course was last modified.
        data_type: date
      - name: grad_subject_area
        description: Graduation subject area (FLDOE GRAD_SUBJECT_AREA).
        data_type: string
      - name: grad_subject_area2
        description: Second graduation subject area.
        data_type: string
      - name: grad_subject_area3
        description: Third graduation subject area.
        data_type: string
      - name: subject_area
        description: Subject area classification.
        data_type: string
      - name: edfi_core_subject
        description: Ed-Fi core subject code.
        data_type: string
      - name: grading_scale
        description: Grading scale applied to the course (FLDOE GRADING_SCALE).
        data_type: string
      - name: standards_grading_scale
        description: Standards grading scale (FLDOE STANDARDS_GRADING_SCALE).
        data_type: string
      - name: grade_posting_scheme
        description: Grade posting scheme (FLDOE GRADE_POSTING_SCHEME).
        data_type: string
      - name: course_history_term
        description: Course history term (FLDOE COURSE_HISTORY_TERM).
        data_type: string
      - name: course_level
        description: Course level classification (FLDOE COURSE_LEVEL).
        data_type: string
      - name: course_length
        description: Course length classification.
        data_type: string
      - name: affects_gpa
        description: Whether the course affects GPA (FLDOE AFFECTS_GPA).
        data_type: numeric
      - name: credits
        description: Credits awarded by the course (FLDOE CREDITS).
        data_type: numeric
      - name: total_credit
        description: Total credit for the course (FLDOE TOTAL_CREDIT).
        data_type: numeric
      - name: credit_hours
        description: Credit hours awarded by the course.
        data_type: numeric
      - name: course_hours
        description: Instructional course hours.
        data_type: numeric
      - name: fee
        description: Course fee (FLDOE FEE).
        data_type: numeric
      - name: low_grade
        description: Lowest grade level for the course (FLDOE LOW_GRADE).
        data_type: string
      - name: high_grade
        description: Highest grade level for the course (FLDOE HIGH_GRADE).
        data_type: string
      - name: gender_restriction
        description:
          Gender restriction on the course (FLDOE GENDER_RESTRICTION).
        data_type: string
      - name: status
        description: Active status of the course (FLDOE ACTIVE).
        data_type: int
      - name: ib
        description: Y/N — whether the course is an IB course (FLDOE IB).
        data_type: string
      - name: ap
        description: Y/N — whether the course is an AP course (FLDOE AP).
        data_type: string
      - name: ell
        description: Y/N — whether the course is an ELL course (FLDOE ELL).
        data_type: string
      - name: certification_requirements
        description:
          CCD certification requirements (FLDOE CERTIFICATION_REQUIREMENTS).
        data_type: string
      - name: course_description
        description: Free-text course description.
        data_type: string
      - name: allow_repeat
        description: Whether the course may be repeated.
        data_type: numeric
      - name: homeroom
        description: Y/N — whether the course is a homeroom.
        data_type: string
      - name: edfi_course_level_characteristic
        description: Ed-Fi course-level characteristic code.
        data_type: string
      - name: iet_program_number
        description: IET program number associated with the course.
        data_type: string
      - name: imported
        description: Y/N — whether the row originated from an import.
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
`uv run dbt build --select stg_focus__master_courses --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `course_id` PASS. Watch the typed
columns: `affects_gpa` / `credits` / `total_credit` / `fee` / `allow_repeat` are
`numeric`; `status` is `int`; the four date columns are `date` (NOT
`timestamp`). Match the YAML to the warehouse type exactly or the contract
fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__master_courses.sql src/dbt/focus/models/staging/properties/stg_focus__master_courses.yml
git commit -m "feat(dbt): add stg_focus__master_courses (#4213)"
```

---

### Task 8: `stg_focus__course_periods` (WIDE — curated)

`course_periods` has 289 columns. The massive long tail —
`custom_1`–`custom_39`, `cp_checkbox_setting_*`, and the entire per-co-teacher
family (`co_teacher_id1`–`10`, `co_teacher*_custom*`, `co_teacher*_checkbox*`,
`co_teacher*_permissions`, `co_teacher*_report_doe`, `co_teacher*_start_date` /
`_end_date` / `_start_time` / `_end_time`, `co_teacher*_out_reason`) — is OUT OF
SCOPE here (Batch H unpivot for `custom_*`; the co-teacher columns belong to the
`co_teacher_days` grain / a future scheduling intermediate). Curate to the
section's canonical definition: section/course/period keys, teacher, room/seats,
the does\_\* and gpa flags, days/calendar/grade-scale, the lead co-teacher ids
(`co_teacher_id1`–`10` ARE FLDOE-mapped, so keep those ten ids by name but NOT
their per-co-teacher attribute columns), and `uuid`/`created_at`/`updated_at`.
PK is `course_period_id`.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__course_periods.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__course_periods.yml`

**Interfaces:**

- Consumes: `source("focus", "course_periods")`
- Produces: model `stg_focus__course_periods`, grain one row per
  `course_period_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    course_period_id,
    syear,
    school_id,
    course_id,
    parent_id,
    rollover_id,
    period_id,
    end_period_id,
    marking_period_id,
    teacher_id,
    co_teacher_id1,
    co_teacher_id2,
    co_teacher_id3,
    co_teacher_id4,
    co_teacher_id5,
    co_teacher_id6,
    co_teacher_id7,
    co_teacher_id8,
    co_teacher_id9,
    co_teacher_id10,
    calendar_id,
    grade_scale_id,
    standards_grade_scale_id,
    grade_posting_scheme_id,
    bell_schedule_id,
    team_id,
    location_id,
    title,
    short_name,
    custom_title,
    room,
    display_room,
    days,
    rotation_days,
    grade_levels,
    course_weight,
    mp,
    course_history_term,
    total_seats,
    filled_seats,
    sped_seats,
    ell_seats,
    credits,
    availability,
    gender_restriction,
    house_restriction,
    does_attendance,
    does_grades,
    does_gpa,
    active,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "course_periods") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__course_periods
    description: >-
      Focus course periods (sections) — one row per scheduled section, scoped by
      school year and school. Curated to the section's canonical definition:
      section/course/period/marking-period keys, the lead and ten co-teacher
      ids, room/seats, scheduling days, and the does_* flags. The custom-field
      long tail and the per-co-teacher attribute columns are excluded; custom_*
      is handled by the Batch H unpivot.
    columns:
      - name: course_period_id
        description: Primary key — Focus course period (section) id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: syear
        description: Focus school year (start year, FLDOE SYEAR).
        data_type: int
      - name: school_id
        description: Focus school number (FLDOE SCHOOL_ID).
        data_type: int
      - name: course_id
        description: Focus course id this section belongs to (FLDOE COURSE_ID).
        data_type: int
      - name: parent_id
        description: Parent course period id for linked sections.
        data_type: int
      - name: rollover_id
        description: Source course period id this rolled over from.
        data_type: int
      - name: period_id
        description: Focus school period id the section meets in.
        data_type: int
      - name: end_period_id
        description: Ending school period id for multi-period sections.
        data_type: int
      - name: marking_period_id
        description: Focus marking period id (FLDOE MARKING_PERIOD_ID).
        data_type: int
      - name: teacher_id
        description: Focus staff id of the lead teacher (FLDOE TEACHER_ID).
        data_type: int
      - name: co_teacher_id1
        description: Co-teacher 1 staff id (FLDOE CO_TEACHER_ID1).
        data_type: int
      - name: co_teacher_id2
        description: Co-teacher 2 staff id (FLDOE CO_TEACHER_ID2).
        data_type: int
      - name: co_teacher_id3
        description: Co-teacher 3 staff id (FLDOE CO_TEACHER_ID3).
        data_type: int
      - name: co_teacher_id4
        description: Co-teacher 4 staff id (FLDOE CO_TEACHER_ID4).
        data_type: int
      - name: co_teacher_id5
        description: Co-teacher 5 staff id (FLDOE CO_TEACHER_ID5).
        data_type: int
      - name: co_teacher_id6
        description: Co-teacher 6 staff id (FLDOE CO_TEACHER_ID6).
        data_type: int
      - name: co_teacher_id7
        description: Co-teacher 7 staff id (FLDOE CO_TEACHER_ID7).
        data_type: int
      - name: co_teacher_id8
        description: Co-teacher 8 staff id (FLDOE CO_TEACHER_ID8).
        data_type: int
      - name: co_teacher_id9
        description: Co-teacher 9 staff id (FLDOE CO_TEACHER_ID9).
        data_type: int
      - name: co_teacher_id10
        description: Co-teacher 10 staff id (FLDOE CO_TEACHER_ID10).
        data_type: int
      - name: calendar_id
        description: Focus calendar id the section follows (FLDOE CALENDAR_ID).
        data_type: int
      - name: grade_scale_id
        description: Grading scale id for the section (FLDOE GRADE_SCALE_ID).
        data_type: int
      - name: standards_grade_scale_id
        description: Standards grading scale id for the section.
        data_type: int
      - name: grade_posting_scheme_id
        description: Grade posting scheme id for the section.
        data_type: int
      - name: bell_schedule_id
        description: Bell schedule id the section is tied to.
        data_type: int
      - name: team_id
        description: Team id the section belongs to.
        data_type: int
      - name: location_id
        description: Location id the section meets at.
        data_type: int
      - name: title
        description: Full section title.
        data_type: string
      - name: short_name
        description: Section number / abbreviated label (FLDOE SHORT_NAME).
        data_type: string
      - name: custom_title
        description: Custom display title for the section.
        data_type: string
      - name: room
        description: Room assigned to the section (FLDOE ROOM).
        data_type: string
      - name: display_room
        description: Display label for the section's room.
        data_type: string
      - name: days
        description: Days of the week the section meets (FLDOE DAYS).
        data_type: string
      - name: rotation_days
        description: Rotation days the section meets.
        data_type: string
      - name: grade_levels
        description: Grade levels the section serves.
        data_type: string
      - name: course_weight
        description: Course weight label applied to the section.
        data_type: string
      - name: mp
        description: Marking period scope for the section.
        data_type: string
      - name: course_history_term
        description: Course history term for the section.
        data_type: string
      - name: total_seats
        description: Total seats in the section (FLDOE TOTAL_SEATS).
        data_type: numeric
      - name: filled_seats
        description: Currently filled seats in the section.
        data_type: numeric
      - name: sped_seats
        description: SPED seats reserved in the section.
        data_type: numeric
      - name: ell_seats
        description: ELL seats reserved in the section.
        data_type: int
      - name: credits
        description: Credits awarded by the section.
        data_type: string
      - name: availability
        description: Availability value for the section.
        data_type: numeric
      - name: gender_restriction
        description:
          Gender restriction on the section (FLDOE GENDER_RESTRICTION).
        data_type: string
      - name: house_restriction
        description: House restriction on the section.
        data_type: string
      - name: does_attendance
        description:
          Y/N — whether the section takes attendance (FLDOE DOES_ATTENDANCE).
        data_type: string
      - name: does_grades
        description: Y/N — whether the section is graded (FLDOE DOES_GRADES).
        data_type: string
      - name: does_gpa
        description:
          Y/N — whether the section counts toward GPA (FLDOE DOES_GPA).
        data_type: string
      - name: active
        description: Y/N — whether the section is active (FLDOE ACTIVE).
        data_type: string
      - name: imported
        description: Y/N — whether the row originated from an import.
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
`uv run dbt build --select stg_focus__course_periods --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `course_period_id` PASS. Watch the
typed columns: `total_seats` / `filled_seats` / `sped_seats` / `availability`
are `numeric`; `ell_seats` is `int`; `credits` is `string` (NOT numeric in this
table). Match the YAML to the warehouse type exactly or the contract fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__course_periods.sql src/dbt/focus/models/staging/properties/stg_focus__course_periods.yml
git commit -m "feat(dbt): add stg_focus__course_periods (#4213)"
```

---

## Final verification

- [ ] **Build all eight together:**

```bash
uv run dbt build --select stg_focus__course_subjects stg_focus__course_weights stg_focus__course_code_directory stg_focus__co_teacher_days stg_focus__resources stg_focus__courses stg_focus__master_courses stg_focus__course_periods --project-dir src/dbt/kippmiami
```

Expected: 8 models build, 16 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook). Run from inside the worktree
      (`/workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance`):

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__course_subjects.sql \
  src/dbt/focus/models/staging/stg_focus__course_weights.sql \
  src/dbt/focus/models/staging/stg_focus__course_code_directory.sql \
  src/dbt/focus/models/staging/stg_focus__co_teacher_days.sql \
  src/dbt/focus/models/staging/stg_focus__resources.sql \
  src/dbt/focus/models/staging/stg_focus__courses.sql \
  src/dbt/focus/models/staging/stg_focus__master_courses.sql \
  src/dbt/focus/models/staging/stg_focus__course_periods.sql \
  src/dbt/focus/models/staging/properties/stg_focus__course_subjects.yml \
  src/dbt/focus/models/staging/properties/stg_focus__course_weights.yml \
  src/dbt/focus/models/staging/properties/stg_focus__course_code_directory.yml \
  src/dbt/focus/models/staging/properties/stg_focus__co_teacher_days.yml \
  src/dbt/focus/models/staging/properties/stg_focus__resources.yml \
  src/dbt/focus/models/staging/properties/stg_focus__courses.yml \
  src/dbt/focus/models/staging/properties/stg_focus__master_courses.yml \
  src/dbt/focus/models/staging/properties/stg_focus__course_periods.yml
```

## Out of scope (other plans / issues)

- **Custom-field unpivot (Batch H)** — the `custom_*` / `custom_field_*` long
  tail on `courses`, `master_courses`, and `course_periods` (and the
  per-co-teacher attribute columns on `course_periods`) unpivots to a long
  key/value model joined to the `custom_fields` metadata crosswalk. Not here.
- **Intermediate scheduling models** — joining sections to teachers, calendars,
  and the `co_teacher_days` grain belongs in a later `int_focus__*` layer.
- **kipptaf region source + `stg_kippmiami__focus__*` wrappers** — deferred to
  the kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all eight Batch D tables have a staging task — narrow
   (`course_subjects`, `course_weights`, `course_code_directory`,
   `co_teacher_days`, `resources`) and wide-curated (`courses`,
   `master_courses`, `course_periods`). ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command. No TBD/TODO/"similar to". ✓
3. **PK correctness:** PKs verified against the warehouse — `subject_id`
   (course_subjects), `id` (course_weights, course_code_directory,
   co_teacher_days, resources), `course_id` (courses, master_courses),
   `course_period_id` (course_periods). Each has `unique` + `not_null` at
   `severity: error`. ✓
4. **Soft-delete:** none of the eight tables has a `deleted` column; no filter
   applied. `course_periods.active` and `master_courses.status` kept as raw
   columns (semantics unconfirmed). ✓
5. **Exclusions:** every model drops `_dlt_*` and the audit-quad
   (`created_by_class`/`_id`, `updated_by_class`/`_id`); keeps
   `uuid`/`created_at`/`updated_at`. ✓
6. **Wide curation:** `courses`/`master_courses`/`course_periods` project only
   the import-mapped core + keys/dates/names + the kept FLDOE `custom_NNN` slots
   (`courses.custom_2`, `courses.custom_10`) and the ten mapped
   `course_periods.co_teacher_idN`; the `custom_*` / per-co-teacher long tail is
   excluded and noted as Batch H. ✓
7. **Type consistency:** each YAML `data_type` matches the warehouse type from
   `INFORMATION_SCHEMA.COLUMNS` (int/string/numeric/date/timestamp). Re-verify
   the typed-column warnings called out in Tasks 6–8 during build (notably
   `course_periods.credits` = string, `master_courses` date-vs-timestamp). ✓
