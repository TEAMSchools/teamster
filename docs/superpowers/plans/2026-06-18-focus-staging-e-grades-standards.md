# Focus Staging — Grades & Standards (Batch E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the 14
populated Focus grades & standards tables (`report_card_grades`,
`report_card_grade_scales`, `report_card_comments`, `grad_subjects`,
`grad_subject_credits`, `standards`, `standard_categories_1` through
`standard_categories_4`, `standards_join_courses`, `gradebook_assignments`,
`gradebook_assignment_types`, `gradebook_templates`) in the `focus`
source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
uniqueness + `not_null` test on each table's primary key, and a `description:`
on the model and every column. Models build inside the consuming district
project (`kippmiami`), which sets `focus_schema` and imports the `focus`
package.

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
- **No soft-delete in this batch:** none of the 14 tables has a `deleted` column
  (verified against `INFORMATION_SCHEMA.COLUMNS`), so no `where deleted is null`
  filter is added anywhere here.
- **No wide-table curation in this batch:** all 14 tables are narrow (≤36
  non-excluded columns; `gradebook_assignments` is the widest at 36). None
  carries a `custom_*` long-tail, so the Batch H custom-field unpivot does not
  apply and every non-excluded column is enumerated. (The Batch H unpivot
  remains out of scope here.)
- **PK per table** (uniqueness target — all verified unique + not-null in the
  warehouse):
  - `id`: `report_card_grades`, `report_card_grade_scales`,
    `report_card_comments`, `grad_subjects`, `grad_subject_credits`,
    `standards`, `standard_categories_1`–`4`, `standards_join_courses`,
    `gradebook_templates`
  - `assignment_id`: `gradebook_assignments`
  - `assignment_type_id`: `gradebook_assignment_types`
- `BOOL` columns stay raw `bool` in this batch (no `is_` rename / conversion) —
  contract `data_type: boolean`. `gradebook_assignments` and
  `gradebook_templates` are the only tables with `BOOL` columns. Y/N-style
  `STRING` flags also stay raw `string`.
- Focus columns are already `snake_case`; the only BigQuery-reserved column name
  in this batch is `language` (`grad_subject_credits`). Backtick-quote it in SQL
  (`` `language` ``) and set `quote: true` in its YAML column entry. No
  self-alias (AL09) — keep it as a bare backticked column. The `sql` column on
  `grad_subject_credits` is NOT reserved in BigQuery and needs no quoting.
- Build/test context is the **kippmiami** project, not `focus` standalone.

### Warehouse `data_type` → contract YAML spelling

The warehouse `INFORMATION_SCHEMA.COLUMNS.data_type` for these tables uses
`INT64` / `NUMERIC` / `STRING` / `TIMESTAMP` / `DATE` / `BOOL`. Contract YAML
declares them as `int` / `numeric` / `string` / `timestamp` / `date` / `boolean`
respectively (BQ legacy-spelling synonyms; `numeric` ≠ `float64` — never
substitute). Each task's YAML below already uses the correct spelling per
column.

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__report_card_grades`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__report_card_grades.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__report_card_grades.yml`

**Interfaces:**

- Consumes: `source("focus", "report_card_grades")`
- Produces: model `stg_focus__report_card_grades`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    title,
    sort_order,
    gpa_value,
    default_breakoff,
    scale_id,
    credits,
    weighted_gpa_value,
    description,
    is_incomplete,
    exclude_grades,
    uuid,
    gpa_averaging_cutoff,
    gpa_averaging_points,
    created_at,
    updated_at,
from {{ source("focus", "report_card_grades") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__report_card_grades
    description: >-
      Focus report card grade definitions — one row per grade mark per school
      year and school. Defines the displayable grade, its GPA value, and credit
      behavior.
    columns:
      - name: id
        description: Primary key — Focus report card grade id.
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
        description: Focus school id the grade belongs to.
        data_type: int
      - name: title
        description: Displayable grade label (e.g. the letter or mark).
        data_type: string
      - name: sort_order
        description: Display sort order within the grade list.
        data_type: numeric
      - name: gpa_value
        description: Unweighted GPA points awarded for this grade.
        data_type: numeric
      - name: default_breakoff
        description: Default minimum percent at which this grade is assigned.
        data_type: numeric
      - name: scale_id
        description: Focus report card grade scale id this grade belongs to.
        data_type: int
      - name: credits
        description: Credits awarded for this grade, stored as text.
        data_type: string
      - name: weighted_gpa_value
        description: Weighted GPA points awarded for this grade.
        data_type: numeric
      - name: description
        description: Long-form description of the grade.
        data_type: string
      - name: is_incomplete
        description: Y/N — whether the grade represents an incomplete.
        data_type: string
      - name: exclude_grades
        description: Y/N — whether the grade is excluded from GPA calculations.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: gpa_averaging_cutoff
        description: Percent cutoff used when averaging into this grade.
        data_type: numeric
      - name: gpa_averaging_points
        description: GPA points used when averaging into this grade.
        data_type: numeric
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__report_card_grades --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS. A contract mismatch
here means a `data_type` in the YAML disagrees with the warehouse — fix the YAML
to match `INFORMATION_SCHEMA.COLUMNS`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__report_card_grades.sql src/dbt/focus/models/staging/properties/stg_focus__report_card_grades.yml
git commit -m "feat(dbt): add stg_focus__report_card_grades (#4213)"
```

---

### Task 2: `stg_focus__report_card_grade_scales`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__report_card_grade_scales.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__report_card_grade_scales.yml`

**Interfaces:**

- Consumes: `source("focus", "report_card_grade_scales")`
- Produces: model `stg_focus__report_card_grade_scales`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    title,
    default_scale,
    rollover_id,
    letter_only,
    show_average_in_gradebook,
    course_level,
    proficiency_gradebook,
    max_post_percent,
    min_post_percent,
    suppress_numeric_proficiency_grades,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "report_card_grade_scales") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__report_card_grade_scales
    description: >-
      Focus report card grade scales — one row per grade scale per school year
      and school. Groups report card grades and governs posting and proficiency
      behavior.
    columns:
      - name: id
        description: Primary key — Focus report card grade scale id.
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
        description: Focus school id the scale belongs to.
        data_type: int
      - name: title
        description: Full grade scale name.
        data_type: string
      - name: default_scale
        description: Y/N — whether this is the school's default grade scale.
        data_type: string
      - name: rollover_id
        description: Source grade scale id this rolled over from.
        data_type: int
      - name: letter_only
        description: Y/N — whether the scale posts letter grades only.
        data_type: string
      - name: show_average_in_gradebook
        description: Y/N — whether the gradebook shows a running average.
        data_type: string
      - name: course_level
        description: Course level the scale applies to.
        data_type: string
      - name: proficiency_gradebook
        description: Y/N — whether the scale drives a proficiency gradebook.
        data_type: string
      - name: max_post_percent
        description: Maximum percent allowed when posting on this scale.
        data_type: int
      - name: min_post_percent
        description: Minimum percent allowed when posting on this scale.
        data_type: int
      - name: suppress_numeric_proficiency_grades
        description: Y/N — whether numeric proficiency grades are suppressed.
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
`uv run dbt build --select stg_focus__report_card_grade_scales --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__report_card_grade_scales.sql src/dbt/focus/models/staging/properties/stg_focus__report_card_grade_scales.yml
git commit -m "feat(dbt): add stg_focus__report_card_grade_scales (#4213)"
```

---

### Task 3: `stg_focus__report_card_comments`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__report_card_comments.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__report_card_comments.yml`

**Interfaces:**

- Consumes: `source("focus", "report_card_comments")`
- Produces: model `stg_focus__report_card_comments`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    title,
    code,
    created_at,
    updated_at,
from {{ source("focus", "report_card_comments") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__report_card_comments
    description: >-
      Focus report card comment bank — one row per canned comment per school
      year and school. Lookup for comment codes applied to report cards.
    columns:
      - name: id
        description: Primary key — Focus report card comment id.
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
        description: Focus school id the comment belongs to.
        data_type: int
      - name: title
        description: Comment text.
        data_type: string
      - name: code
        description: Short code identifying the comment.
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
`uv run dbt build --select stg_focus__report_card_comments --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__report_card_comments.sql src/dbt/focus/models/staging/properties/stg_focus__report_card_comments.yml
git commit -m "feat(dbt): add stg_focus__report_card_comments (#4213)"
```

---

### Task 4: `stg_focus__grad_subjects`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__grad_subjects.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__grad_subjects.yml`

**Interfaces:**

- Consumes: `source("focus", "grad_subjects")`
- Produces: model `stg_focus__grad_subjects`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    title,
    short_name,
    sort_order,
    credits,
    rollover_id,
    request_group,
    ahs_subject,
    min_syear,
    max_syear,
    district_id,
    created_at,
    updated_at,
from {{ source("focus", "grad_subjects") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__grad_subjects
    description: >-
      Focus graduation subjects — one row per graduation-requirement subject
      area used to organize credit requirements.
    columns:
      - name: id
        description: Primary key — Focus graduation subject id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Full graduation subject name.
        data_type: string
      - name: short_name
        description: Abbreviated graduation subject label.
        data_type: string
      - name: sort_order
        description: Display sort order within the subject list.
        data_type: numeric
      - name: credits
        description: Default credits associated with the subject.
        data_type: numeric
      - name: rollover_id
        description: Source graduation subject id this rolled over from.
        data_type: int
      - name: request_group
        description: Course-request grouping id for the subject.
        data_type: int
      - name: ahs_subject
        description: Adult-high-school subject mapping value.
        data_type: string
      - name: min_syear
        description: Earliest school year the subject applies to.
        data_type: int
      - name: max_syear
        description: Latest school year the subject applies to.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__grad_subjects --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__grad_subjects.sql src/dbt/focus/models/staging/properties/stg_focus__grad_subjects.yml
git commit -m "feat(dbt): add stg_focus__grad_subjects (#4213)"
```

---

### Task 5: `stg_focus__grad_subject_credits`

`grad_subject_credits` is the only table in this batch with a BigQuery-reserved
column name (`language`). It is backtick-quoted in the SQL and flagged
`quote: true` in the YAML. The `grad_subject_id` column is `STRING` in the
warehouse (NOT `int`) — declare it `string`.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__grad_subject_credits.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__grad_subject_credits.yml`

**Interfaces:**

- Consumes: `source("focus", "grad_subject_credits")`
- Produces: model `stg_focus__grad_subject_credits`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    grad_subject_id,
    grad_program_id,
    credits,
    sql,
    title,
    type,
    sort_order,
    grade_level_short_name,
    `language`,
    created_at,
    updated_at,
from {{ source("focus", "grad_subject_credits") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__grad_subject_credits
    description: >-
      Focus graduation subject credit requirements — one row per credit rule
      linking a graduation subject to a graduation program and required credits.
    columns:
      - name: id
        description: Primary key — Focus graduation subject credit id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: grad_subject_id
        description: Focus graduation subject id, stored as text.
        data_type: string
      - name: grad_program_id
        description: Focus graduation program id this credit rule belongs to.
        data_type: int
      - name: credits
        description: Required credits for this subject within the program.
        data_type: numeric
      - name: sql
        description: Optional SQL predicate scoping the credit rule.
        data_type: string
      - name: title
        description: Credit rule label.
        data_type: string
      - name: type
        description: Credit rule type classification.
        data_type: string
      - name: sort_order
        description: Display sort order within the credit rule list.
        data_type: int
      - name: grade_level_short_name
        description: Short name of the grade level the rule applies to.
        data_type: string
      - name: language
        description: Language scope for the credit rule.
        data_type: string
        quote: true
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__grad_subject_credits --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. If the build errors on
`language`, confirm the SQL backtick-quotes it and the YAML entry sets
`quote: true` (both are required for a reserved word).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__grad_subject_credits.sql src/dbt/focus/models/staging/properties/stg_focus__grad_subject_credits.yml
git commit -m "feat(dbt): add stg_focus__grad_subject_credits (#4213)"
```

---

### Task 6: `stg_focus__standards`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__standards.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__standards.yml`

**Interfaces:**

- Consumes: `source("focus", "standards")`
- Produces: model `stg_focus__standards`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    description,
    sort_order,
    category_1_id,
    category_2_id,
    category_3_id,
    category_4_id,
    rollover_id,
    marking_periods,
    hide_on_report_card,
    cte_import,
    cpalms,
    grade_scale_title,
    guid,
    implementation_year,
    obsolete_year,
    adopt_year,
    publication,
    created_at,
    updated_at,
from {{ source("focus", "standards") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__standards
    description: >-
      Focus learning standards — one row per standard, linked to up to four
      nested standard categories and scoped by school year, school, and
      district.
    columns:
      - name: id
        description: Primary key — Focus standard id.
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
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full standard text.
        data_type: string
      - name: short_name
        description: Abbreviated standard label or code.
        data_type: string
      - name: description
        description: Long-form description of the standard.
        data_type: string
      - name: sort_order
        description: Display sort order within the standard list.
        data_type: numeric
      - name: category_1_id
        description: Level-1 standard category id (standard_categories_1).
        data_type: int
      - name: category_2_id
        description: Level-2 standard category id (standard_categories_2).
        data_type: int
      - name: category_3_id
        description: Level-3 standard category id (standard_categories_3).
        data_type: int
      - name: category_4_id
        description: Level-4 standard category id (standard_categories_4).
        data_type: int
      - name: rollover_id
        description: Source standard id this rolled over from.
        data_type: int
      - name: marking_periods
        description: Marking periods the standard is assessed in.
        data_type: string
      - name: hide_on_report_card
        description: Y/N — whether the standard is hidden on report cards.
        data_type: string
      - name: cte_import
        description: Career and technical education import marker.
        data_type: string
      - name: cpalms
        description: Florida CPALMS identifier for the standard.
        data_type: int
      - name: grade_scale_title
        description: Grade scale title the standard is assessed on.
        data_type: string
      - name: guid
        description: Focus global unique identifier for the standard.
        data_type: string
      - name: implementation_year
        description: Year the standard takes effect.
        data_type: int
      - name: obsolete_year
        description: Year the standard becomes obsolete.
        data_type: int
      - name: adopt_year
        description: Year the standard was adopted.
        data_type: int
      - name: publication
        description: Source publication the standard belongs to.
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
`uv run dbt build --select stg_focus__standards --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__standards.sql src/dbt/focus/models/staging/properties/stg_focus__standards.yml
git commit -m "feat(dbt): add stg_focus__standards (#4213)"
```

---

### Task 7: `stg_focus__standard_categories_1`

The four `standard_categories_*` tables share nearly identical schemas. Level 1
has NO `parent_id` (it is the root level); levels 2-4 each add `parent_id`.
Column order differs slightly between the warehouse tables (e.g. `cte_import`
position) but contract enforcement matches by name + type, not order — the SQL
column order below is the human-readable order, not the warehouse order.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__standard_categories_1.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__standard_categories_1.yml`

**Interfaces:**

- Consumes: `source("focus", "standard_categories_1")`
- Produces: model `stg_focus__standard_categories_1`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    sort_order,
    rollover_id,
    cte_import,
    cpalms,
    guid,
    created_at,
    updated_at,
from {{ source("focus", "standard_categories_1") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__standard_categories_1
    description: >-
      Focus level-1 (root) standard categories — one row per top-level grouping
      of learning standards, scoped by school year, school, and district.
    columns:
      - name: id
        description: Primary key — Focus level-1 standard category id.
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
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full category name.
        data_type: string
      - name: short_name
        description: Abbreviated category label.
        data_type: string
      - name: sort_order
        description: Display sort order within the category list.
        data_type: numeric
      - name: rollover_id
        description: Source category id this rolled over from.
        data_type: int
      - name: cte_import
        description: Career and technical education import marker.
        data_type: string
      - name: cpalms
        description: Florida CPALMS identifier for the category.
        data_type: int
      - name: guid
        description: Focus global unique identifier for the category.
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
`uv run dbt build --select stg_focus__standard_categories_1 --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__standard_categories_1.sql src/dbt/focus/models/staging/properties/stg_focus__standard_categories_1.yml
git commit -m "feat(dbt): add stg_focus__standard_categories_1 (#4213)"
```

---

### Task 8: `stg_focus__standard_categories_2`

Identical to level 1 but adds `parent_id` (FK to `standard_categories_1.id`).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__standard_categories_2.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__standard_categories_2.yml`

**Interfaces:**

- Consumes: `source("focus", "standard_categories_2")`
- Produces: model `stg_focus__standard_categories_2`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    parent_id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    sort_order,
    rollover_id,
    cte_import,
    cpalms,
    guid,
    created_at,
    updated_at,
from {{ source("focus", "standard_categories_2") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__standard_categories_2
    description: >-
      Focus level-2 standard categories — one row per second-level grouping of
      learning standards, nested under a level-1 category via parent_id.
    columns:
      - name: id
        description: Primary key — Focus level-2 standard category id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: parent_id
        description:
          Level-1 standard category id (standard_categories_1) this nests under.
        data_type: int
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: school_id
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full category name.
        data_type: string
      - name: short_name
        description: Abbreviated category label.
        data_type: string
      - name: sort_order
        description: Display sort order within the category list.
        data_type: numeric
      - name: rollover_id
        description: Source category id this rolled over from.
        data_type: int
      - name: cte_import
        description: Career and technical education import marker.
        data_type: string
      - name: cpalms
        description: Florida CPALMS identifier for the category.
        data_type: int
      - name: guid
        description: Focus global unique identifier for the category.
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
`uv run dbt build --select stg_focus__standard_categories_2 --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__standard_categories_2.sql src/dbt/focus/models/staging/properties/stg_focus__standard_categories_2.yml
git commit -m "feat(dbt): add stg_focus__standard_categories_2 (#4213)"
```

---

### Task 9: `stg_focus__standard_categories_3`

Identical to level 2 but `parent_id` references `standard_categories_2.id`.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__standard_categories_3.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__standard_categories_3.yml`

**Interfaces:**

- Consumes: `source("focus", "standard_categories_3")`
- Produces: model `stg_focus__standard_categories_3`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    parent_id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    sort_order,
    rollover_id,
    cte_import,
    cpalms,
    guid,
    created_at,
    updated_at,
from {{ source("focus", "standard_categories_3") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__standard_categories_3
    description: >-
      Focus level-3 standard categories — one row per third-level grouping of
      learning standards, nested under a level-2 category via parent_id.
    columns:
      - name: id
        description: Primary key — Focus level-3 standard category id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: parent_id
        description:
          Level-2 standard category id (standard_categories_2) this nests under.
        data_type: int
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: school_id
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full category name.
        data_type: string
      - name: short_name
        description: Abbreviated category label.
        data_type: string
      - name: sort_order
        description: Display sort order within the category list.
        data_type: numeric
      - name: rollover_id
        description: Source category id this rolled over from.
        data_type: int
      - name: cte_import
        description: Career and technical education import marker.
        data_type: string
      - name: cpalms
        description: Florida CPALMS identifier for the category.
        data_type: int
      - name: guid
        description: Focus global unique identifier for the category.
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
`uv run dbt build --select stg_focus__standard_categories_3 --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__standard_categories_3.sql src/dbt/focus/models/staging/properties/stg_focus__standard_categories_3.yml
git commit -m "feat(dbt): add stg_focus__standard_categories_3 (#4213)"
```

---

### Task 10: `stg_focus__standard_categories_4`

Identical to level 3 but `parent_id` references `standard_categories_3.id`.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__standard_categories_4.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__standard_categories_4.yml`

**Interfaces:**

- Consumes: `source("focus", "standard_categories_4")`
- Produces: model `stg_focus__standard_categories_4`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    parent_id,
    syear,
    school_id,
    district_id,
    title,
    short_name,
    sort_order,
    rollover_id,
    cte_import,
    cpalms,
    guid,
    created_at,
    updated_at,
from {{ source("focus", "standard_categories_4") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__standard_categories_4
    description: >-
      Focus level-4 (leaf) standard categories — one row per fourth-level
      grouping of learning standards, nested under a level-3 category via
      parent_id.
    columns:
      - name: id
        description: Primary key — Focus level-4 standard category id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: parent_id
        description:
          Level-3 standard category id (standard_categories_3) this nests under.
        data_type: int
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: school_id
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: title
        description: Full category name.
        data_type: string
      - name: short_name
        description: Abbreviated category label.
        data_type: string
      - name: sort_order
        description: Display sort order within the category list.
        data_type: numeric
      - name: rollover_id
        description: Source category id this rolled over from.
        data_type: int
      - name: cte_import
        description: Career and technical education import marker.
        data_type: string
      - name: cpalms
        description: Florida CPALMS identifier for the category.
        data_type: int
      - name: guid
        description: Focus global unique identifier for the category.
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
`uv run dbt build --select stg_focus__standard_categories_4 --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__standard_categories_4.sql src/dbt/focus/models/staging/properties/stg_focus__standard_categories_4.yml
git commit -m "feat(dbt): add stg_focus__standard_categories_4 (#4213)"
```

---

### Task 11: `stg_focus__standards_join_courses`

Join table linking standards to courses. Despite being a junction table it
carries a surrogate `id` that is unique + not-null in the warehouse (verified:
180,306 rows, 180,306 distinct `id`) — use `id` as the PK. The link columns are
`standard_id` (FK to `standards.id`) and `course_num` (the course-number string,
NOT a numeric id).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__standards_join_courses.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__standards_join_courses.yml`

**Interfaces:**

- Consumes: `source("focus", "standards_join_courses")`
- Produces: model `stg_focus__standards_join_courses`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    standard_id,
    course_num,
    school_id,
    district_id,
    cpalms,
    created_at,
    updated_at,
from {{ source("focus", "standards_join_courses") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__standards_join_courses
    description: >-
      Focus standard-to-course links — one row per standard mapped to a course
      number. Junction between standards and the course catalog.
    columns:
      - name: id
        description: Primary key — Focus standard-course link id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: standard_id
        description: Focus standard id (standards.id) being linked.
        data_type: int
      - name: course_num
        description: Course number the standard is mapped to, stored as text.
        data_type: string
      - name: school_id
        description: Focus school id.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: cpalms
        description: Florida CPALMS identifier for the link.
        data_type: int
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__standards_join_courses --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__standards_join_courses.sql src/dbt/focus/models/staging/properties/stg_focus__standards_join_courses.yml
git commit -m "feat(dbt): add stg_focus__standards_join_courses (#4213)"
```

---

### Task 12: `stg_focus__gradebook_assignments`

The widest table in this batch (36 non-excluded columns) and the only one with
multiple `BOOL` columns. All `BOOL` columns stay raw (`data_type: boolean`, no
`is_` rename in this batch). The PK is `assignment_id` (NOT `id`). `points` is
`NUMERIC`; `last_updated_user` is `NUMERIC` (not an int id).

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__gradebook_assignments.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments.yml`

**Interfaces:**

- Consumes: `source("focus", "gradebook_assignments")`
- Produces: model `stg_focus__gradebook_assignments`, grain one row per
  `assignment_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    assignment_id,
    assignment_type_id,
    title,
    points,
    description,
    benchmarks,
    questions,
    parent_id,
    prerequisite_assignment,
    template_id,
    template_assignment_id,
    rollover_id,
    copied_from_id,
    rubric_id,
    web_page_id,
    external_api_id,
    external_api_uuid,
    learnosity_activity_id,
    examspark_exam_id,
    apex_assessment_id,
    last_updated_user,
    allow_student_upload,
    no_late_turnin,
    hide_from_excluded,
    exclude_from_average,
    accessibility,
    transfer,
    allow_google_drive,
    allow_onedrive,
    uuid,
    last_updated_date,
    score_release_timestamp,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_assignments") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__gradebook_assignments
    description: >-
      Focus gradebook assignments — one row per assignment, including its point
      value, category, template lineage, and external-tool linkages.
    columns:
      - name: assignment_id
        description: Primary key — Focus gradebook assignment id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: assignment_type_id
        description: Focus gradebook assignment type id (the category).
        data_type: int
      - name: title
        description: Assignment name.
        data_type: string
      - name: points
        description: Total points the assignment is worth.
        data_type: numeric
      - name: description
        description: Assignment description text.
        data_type: string
      - name: benchmarks
        description: Standards or benchmarks tagged on the assignment.
        data_type: string
      - name: questions
        description: Number of questions in the assignment.
        data_type: int
      - name: parent_id
        description: Parent assignment id for nested assignments.
        data_type: int
      - name: prerequisite_assignment
        description: Assignment id that must be completed first.
        data_type: int
      - name: template_id
        description: Gradebook template id the assignment belongs to.
        data_type: int
      - name: template_assignment_id
        description: Source template assignment id this was created from.
        data_type: int
      - name: rollover_id
        description: Source assignment id this rolled over from.
        data_type: int
      - name: copied_from_id
        description: Assignment id this was copied from.
        data_type: int
      - name: rubric_id
        description: Rubric id attached to the assignment.
        data_type: int
      - name: web_page_id
        description: Web page id attached to the assignment.
        data_type: int
      - name: external_api_id
        description: External API integer id for the assignment.
        data_type: int
      - name: external_api_uuid
        description: External API uuid for the assignment.
        data_type: string
      - name: learnosity_activity_id
        description: Learnosity activity id linked to the assignment.
        data_type: string
      - name: examspark_exam_id
        description: ExamSpark exam id linked to the assignment.
        data_type: string
      - name: apex_assessment_id
        description: Apex assessment id linked to the assignment.
        data_type: int
      - name: last_updated_user
        description: Identifier of the user who last updated the assignment.
        data_type: numeric
      - name: allow_student_upload
        description: Whether students may upload files to the assignment.
        data_type: boolean
      - name: no_late_turnin
        description: Whether late turn-ins are disallowed.
        data_type: boolean
      - name: hide_from_excluded
        description: Whether the assignment is hidden from excluded students.
        data_type: boolean
      - name: exclude_from_average
        description: Whether the assignment is excluded from the average.
        data_type: boolean
      - name: accessibility
        description: Whether accessibility features are enabled.
        data_type: boolean
      - name: transfer
        description: Whether the assignment is a transfer assignment.
        data_type: boolean
      - name: allow_google_drive
        description: Whether Google Drive uploads are allowed.
        data_type: boolean
      - name: allow_onedrive
        description: Whether OneDrive uploads are allowed.
        data_type: boolean
      - name: uuid
        description: Focus global unique identifier for the assignment.
        data_type: string
      - name: last_updated_date
        description: Source last-updated timestamp.
        data_type: timestamp
      - name: score_release_timestamp
        description: Timestamp at which scores are released to students.
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
`uv run dbt build --select stg_focus__gradebook_assignments --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `assignment_id` PASS. If a contract
error fires on a `BOOL` column, confirm the YAML declares it `boolean` (the BQ
synonym for `BOOL`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__gradebook_assignments.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments.yml
git commit -m "feat(dbt): add stg_focus__gradebook_assignments (#4213)"
```

---

### Task 13: `stg_focus__gradebook_assignment_types`

PK is `assignment_type_id` (NOT `id`). This is the category lookup for
`gradebook_assignments.assignment_type_id`.

**Files:**

- Create:
  `src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types.yml`

**Interfaces:**

- Consumes: `source("focus", "gradebook_assignment_types")`
- Produces: model `stg_focus__gradebook_assignment_types`, grain one row per
  `assignment_type_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    assignment_type_id,
    title,
    template_id,
    template_category_id,
    rollover_id,
    copied_from_id,
    external_api_id,
    external_api_uuid,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_assignment_types") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__gradebook_assignment_types
    description: >-
      Focus gradebook assignment types — one row per assignment category used to
      group and weight gradebook assignments.
    columns:
      - name: assignment_type_id
        description: Primary key — Focus gradebook assignment type id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Assignment type name.
        data_type: string
      - name: template_id
        description: Gradebook template id the type belongs to.
        data_type: int
      - name: template_category_id
        description: Source template category id this type was created from.
        data_type: int
      - name: rollover_id
        description: Source assignment type id this rolled over from.
        data_type: int
      - name: copied_from_id
        description: Assignment type id this was copied from.
        data_type: int
      - name: external_api_id
        description: External API integer id for the assignment type.
        data_type: int
      - name: external_api_uuid
        description: External API uuid for the assignment type.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the assignment type.
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
`uv run dbt build --select stg_focus__gradebook_assignment_types --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `assignment_type_id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types.yml
git commit -m "feat(dbt): add stg_focus__gradebook_assignment_types (#4213)"
```

---

### Task 14: `stg_focus__gradebook_templates`

PK is `id`. Has one `BOOL` column (`force_weighting` → `data_type: boolean`) and
two `DATE` columns (`created`, `modified` → `data_type: date`). Note both
`created`/`modified` (DATE) AND `created_at`/`updated_at` (TIMESTAMP) exist —
keep all four; they are distinct columns.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__gradebook_templates.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__gradebook_templates.yml`

**Interfaces:**

- Consumes: `source("focus", "gradebook_templates")`
- Produces: model `stg_focus__gradebook_templates`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    title,
    syear,
    district_id,
    staff_id,
    schools,
    global_course,
    enabled,
    rollover_id,
    drop_lowest_grade,
    force_weighting,
    add_category,
    modify_category,
    modify_category_title,
    add_assignment,
    modify_assignment,
    add_standard,
    modify_standard,
    created,
    modified,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_templates") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__gradebook_templates
    description: >-
      Focus gradebook templates — one row per template defining the category,
      assignment, and standard structure a gradebook inherits.
    columns:
      - name: id
        description: Primary key — Focus gradebook template id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Template name.
        data_type: string
      - name: syear
        description: Focus school year (start year).
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: staff_id
        description: Focus staff id that owns the template.
        data_type: int
      - name: schools
        description: Schools the template applies to.
        data_type: string
      - name: global_course
        description: Global course the template is tied to.
        data_type: string
      - name: enabled
        description: Whether the template is enabled (1) or not.
        data_type: int
      - name: rollover_id
        description: Source template id this rolled over from.
        data_type: int
      - name: drop_lowest_grade
        description: Number of lowest grades dropped per category.
        data_type: numeric
      - name: force_weighting
        description: Whether category weighting is forced on inheriting books.
        data_type: boolean
      - name: add_category
        description: Whether inheriting gradebooks may add categories.
        data_type: string
      - name: modify_category
        description: Whether inheriting gradebooks may modify categories.
        data_type: string
      - name: modify_category_title
        description: Whether inheriting gradebooks may rename categories.
        data_type: string
      - name: add_assignment
        description: Whether inheriting gradebooks may add assignments.
        data_type: string
      - name: modify_assignment
        description: Whether inheriting gradebooks may modify assignments.
        data_type: string
      - name: add_standard
        description: Whether inheriting gradebooks may add standards.
        data_type: string
      - name: modify_standard
        description: Whether inheriting gradebooks may modify standards.
        data_type: string
      - name: created
        description: Template creation date.
        data_type: date
      - name: modified
        description: Template last-modified date.
        data_type: date
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__gradebook_templates --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. Watch the `created` /
`modified` (DATE) vs `created_at` / `updated_at` (TIMESTAMP) split — match the
YAML `data_type` exactly or the contract fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__gradebook_templates.sql src/dbt/focus/models/staging/properties/stg_focus__gradebook_templates.yml
git commit -m "feat(dbt): add stg_focus__gradebook_templates (#4213)"
```

---

## Final verification

- [ ] **Build all 14 together:**

```bash
uv run dbt build --select stg_focus__report_card_grades stg_focus__report_card_grade_scales stg_focus__report_card_comments stg_focus__grad_subjects stg_focus__grad_subject_credits stg_focus__standards stg_focus__standard_categories_1 stg_focus__standard_categories_2 stg_focus__standard_categories_3 stg_focus__standard_categories_4 stg_focus__standards_join_courses stg_focus__gradebook_assignments stg_focus__gradebook_assignment_types stg_focus__gradebook_templates --project-dir src/dbt/kippmiami
```

Expected: 14 models build, 28 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook). Run from inside the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__report_card_grades.sql \
  src/dbt/focus/models/staging/stg_focus__report_card_grade_scales.sql \
  src/dbt/focus/models/staging/stg_focus__report_card_comments.sql \
  src/dbt/focus/models/staging/stg_focus__grad_subjects.sql \
  src/dbt/focus/models/staging/stg_focus__grad_subject_credits.sql \
  src/dbt/focus/models/staging/stg_focus__standards.sql \
  src/dbt/focus/models/staging/stg_focus__standard_categories_1.sql \
  src/dbt/focus/models/staging/stg_focus__standard_categories_2.sql \
  src/dbt/focus/models/staging/stg_focus__standard_categories_3.sql \
  src/dbt/focus/models/staging/stg_focus__standard_categories_4.sql \
  src/dbt/focus/models/staging/stg_focus__standards_join_courses.sql \
  src/dbt/focus/models/staging/stg_focus__gradebook_assignments.sql \
  src/dbt/focus/models/staging/stg_focus__gradebook_assignment_types.sql \
  src/dbt/focus/models/staging/stg_focus__gradebook_templates.sql \
  src/dbt/focus/models/staging/properties/stg_focus__report_card_grades.yml \
  src/dbt/focus/models/staging/properties/stg_focus__report_card_grade_scales.yml \
  src/dbt/focus/models/staging/properties/stg_focus__report_card_comments.yml \
  src/dbt/focus/models/staging/properties/stg_focus__grad_subjects.yml \
  src/dbt/focus/models/staging/properties/stg_focus__grad_subject_credits.yml \
  src/dbt/focus/models/staging/properties/stg_focus__standards.yml \
  src/dbt/focus/models/staging/properties/stg_focus__standard_categories_1.yml \
  src/dbt/focus/models/staging/properties/stg_focus__standard_categories_2.yml \
  src/dbt/focus/models/staging/properties/stg_focus__standard_categories_3.yml \
  src/dbt/focus/models/staging/properties/stg_focus__standard_categories_4.yml \
  src/dbt/focus/models/staging/properties/stg_focus__standards_join_courses.yml \
  src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignments.yml \
  src/dbt/focus/models/staging/properties/stg_focus__gradebook_assignment_types.yml \
  src/dbt/focus/models/staging/properties/stg_focus__gradebook_templates.yml
```

## Out of scope (other plans / issues)

- Custom-field unpivot (Batch H) — none of these 14 tables carries a `custom_*`
  long-tail, so there is nothing to defer to Batch H from this batch.
- Fact/intermediate models for posted report card grades and gradebook scores —
  source tables (`student_report_card_grades`, `gradebook_grades`) are empty
  (#4220).
- `is_` boolean renames / Y/N→boolean conversions — deferred to an intermediate
  layer if a consumer needs them; staging keeps `BOOL` raw and Y/N flags as
  `STRING`.
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all 14 Batch E tables have a staging task (Tasks 1-14). ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command. No "similar to Task N" — each `standard_categories_*` task
   repeats its full SQL and YAML. ✓
3. **Type consistency:** each YAML `data_type` matches the warehouse type pulled
   from `INFORMATION_SCHEMA.COLUMNS`. Specific traps verified inline:
   - `grad_subject_id` is `string` (not int) — Task 5.
   - `language` reserved word backtick-quoted + `quote: true` — Task 5.
   - `gradebook_assignments` PK is `assignment_id`, `last_updated_user` is
     `numeric`, all `BOOL` → `boolean` — Task 12.
   - `gradebook_assignment_types` PK is `assignment_type_id` — Task 13.
   - `gradebook_templates` has both `created`/`modified` (DATE) and
     `created_at`/`updated_at` (TIMESTAMP); `force_weighting` → `boolean`,
     `enabled` → `int` — Task 14.
4. **PK uniqueness verified in warehouse:** `id` unique+not-null on the join
   tables (`standards_join_courses` 180,306/180,306; `grad_subject_credits`
   60/60) and the entity tables; `assignment_id` / `assignment_type_id` are the
   PKs for the two gradebook tables. ✓
5. **No soft-delete / no curation:** confirmed none of the 14 tables has a
   `deleted` column and all are narrow (≤36 cols), so no filter and no curation.
   ✓
