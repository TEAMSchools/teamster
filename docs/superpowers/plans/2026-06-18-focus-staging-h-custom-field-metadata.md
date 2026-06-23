# Focus Staging — Custom Field Metadata (Batch H) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the six
populated Focus custom-field metadata tables (`custom_fields`,
`custom_field_categories`, `custom_field_select_options`,
`custom_field_log_columns`, `custom_field_log_entries`,
`custom_fields_join_categories`) in the `focus` source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Staging only — light
cleaning: explicit column projection (drop dlt bookkeeping + audit-quad), a
soft-delete filter where the table has one, `is_`-prefixed renames for true
`BOOL` columns, a uniqueness + `not_null` test on each table's `id` primary key,
and a `description:` on the model and every column. NO unpivot, NO code -> label
decode, NO log-field reshape — those are the deferred Wave 2 follow-up that this
batch's clean metadata powers. Models build inside the consuming district
project (`kippmiami`), which sets `focus_schema` and imports the `focus`
package.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, dbt contracts. SQL per
`.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas, single quotes, 88
cols, lowercase, ST06 column ordering).

## Global Constraints

- Contract enforcement is already set at the `staging` directory level in
  `src/dbt/focus/dbt_project.yml` (`+contract: enforced: true`) — do NOT add
  `{{ config(contract=...) }}` per model. Every column the SQL projects MUST be
  declared in the properties YAML with a matching `data_type`.
- Source is BQ-native: `{{ source("focus", "<table>") }}` (source name `focus`,
  bare table name). Schema resolves from `var("focus_schema")` =
  `dagster_kippmiami_dlt_focus` (set in `src/dbt/kippmiami/dbt_project.yml`).
- Exclude dlt bookkeeping columns (`_dlt_id`, `_dlt_load_id`, any `_dlt_*`) and
  the audit-quad (`created_by_class`, `created_by_id`, `updated_by_class`,
  `updated_by_id`) from every model. Keep `created_at` / `updated_at` / `uuid`
  (where present).
- **Primary key is `id` on all six tables.** Every model gets `unique` +
  `not_null` on `id`, both at `config: severity: error` (project default is
  `warn`, which silently won't fail CI).
- **Soft-delete:** the `deleted INT64` column is `NULL` for live rows and `1`
  for deleted (there is no `0`). Filter `where deleted is null` (NOT `= 0`,
  which matches nothing) and OMIT the `deleted` column from the projection on
  the five tables that have it: `custom_fields`, `custom_field_categories`,
  `custom_field_select_options`, `custom_field_log_columns`,
  `custom_fields_join_categories`. `custom_field_log_entries` has NO `deleted`
  column — no filter, no omission.
- **`inactive` (and `active` / `archived`) are RAW attributes, not soft-delete
  sentinels** — keep them in the projection, do NOT filter on them.
- **True `BOOL` columns get an `is_` prefix** (rename in the staging SQL,
  declare the renamed name in YAML). STRING Y/N flags and `INT64` 0/1 flags stay
  raw (no rename, no boolean cast in this batch). The `BOOL`-typed columns per
  table are called out in each task.
- Focus columns are already `snake_case`. None of the kept columns is a BigQuery
  reserved word, so no backtick-quoting / `quote: true` in this batch.
- **`type` is a kept column on `custom_fields` and `custom_field_log_columns`.**
  `type` is NOT a BigQuery reserved word — leave it unquoted, no `quote: true`.
- ST06 column order in every `SELECT`: plain column refs first (grouped, single
  source so no alias prefix), then the `is_`-renamed boolean refs (these are
  plain-ref renames, group them with the plain refs in source order). No
  constants/functions/case/window are introduced in this batch.
- Unquoted YAML `description:` scalars must NOT contain `': '` (colon-space) and
  must NOT start with a backtick. Use `-` (space-dash-space) or `—` instead of a
  colon, and lead with a word.
- Build/test context is the **kippmiami** project, not `focus` standalone.
- Build command (every task):
  `uv run dbt build --select <model> --project-dir src/dbt/kippmiami`.
- This batch ships as one PR referencing the Phase B tracking issue (#4213).

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

Expected: `Installed N packages` (no "0 package(s) installed" error). If it
reports 0 installed, you are in the wrong project dir.

---

### Task 1: `stg_focus__custom_fields`

`custom_fields` has ~71 raw columns, most of them UI/visibility/kiosk/display
plumbing irrelevant to the decode follow-up. Curate to the decode-relevant +
descriptive metadata and DROP the long tail (`visible_on_*`, `kiosk_*`,
`display_as_*`, `file_upload_*`, `pronunciation_*`, `settings`, `notes`,
`new_record*`, `rich_text`, `system`, `imported`, `migrated`, `legacy_id`,
`restricted`, `is_tag`, `gpt_accessible`, etc.). The kept set is the
field-definition core the unpivot/decode work in Wave 2 needs.

True `BOOL` columns kept: `json`, `focus_manage`, `translate`, `column_adopted`
-> renamed `is_json`, `is_focus_manage`, `is_translate`, `is_column_adopted`.
`required`, `inactive`, `encrypted` are `INT64` 0/1 flags — kept raw.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__custom_fields.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__custom_fields.yml`

**Interfaces:**

- Consumes: `source("focus", "custom_fields")`
- Produces: model `stg_focus__custom_fields`, grain one row per `id` (one Focus
  custom field definition). Downstream Wave 2 decode joins on `id` ->
  `custom_field_select_options.source_id` and slugs `title` to the unpivot
  column alias.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    source_class,
    type,
    title,
    alias,
    column_name,
    description,
    default_value,
    fallback_value,
    option_query,
    computed_query,
    max_length,
    required,
    inactive,
    encrypted,
    district_id,
    uuid,
    created_at,
    updated_at,
    json as is_json,
    focus_manage as is_focus_manage,
    translate as is_translate,
    column_adopted as is_column_adopted,
from {{ source("focus", "custom_fields") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__custom_fields
    description: >-
      Focus custom field definitions — one row per custom field. Curated to the
      decode-relevant and descriptive metadata (type, title, alias, column_name,
      option/computed queries) that powers the deferred unpivot and code ->
      label decode follow-up. UI, visibility, kiosk, and display-plumbing
      columns are intentionally excluded. Live rows only (soft-deleted rows
      filtered out).
    columns:
      - name: id
        description: Primary key — Focus custom field id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: source_class
        description: >-
          Owning entity class for the field (e.g. SISStudent, FocusUser,
          SISSchool, CoursePeriod, CourseCatalog) — maps the field to its host
          table.
        data_type: string
      - name: type
        description: >-
          Field input type (e.g. select, multiple, text, date, numeric,
          checkbox, log, computed). Drives how the stored value is decoded.
        data_type: string
      - name: title
        description:
          Human-readable field label — slug source for the unpivot alias.
        data_type: string
      - name: alias
        description: >-
          Focus field alias — raw custom_NNN for most fields, so not used as the
          unpivot slug source.
        data_type: string
      - name: column_name
        description: Underlying storage column name for the field value.
        data_type: string
      - name: description
        description: Long-form description of the field.
        data_type: string
      - name: default_value
        description: Default value applied when no value is entered.
        data_type: string
      - name: fallback_value
        description: Fallback value used when the stored value is empty.
        data_type: string
      - name: option_query
        description: >-
          Query backing the select/multiple option list — relevant to the decode
          follow-up.
        data_type: string
      - name: computed_query
        description:
          Query used to compute the field value for computed-type fields.
        data_type: string
      - name: max_length
        description: Maximum character length allowed for the field value.
        data_type: int
      - name: required
        description: Flag (0/1) — whether the field is required on entry.
        data_type: int
      - name: inactive
        description: >-
          Raw inactive flag (0/1) — a field attribute, NOT a soft-delete
          sentinel. Inactive fields are retained.
        data_type: int
      - name: encrypted
        description: Flag (0/1) — whether the stored value is encrypted.
        data_type: int
      - name: district_id
        description: Focus district id the field is scoped to.
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
      - name: is_json
        description: Boolean — whether the field stores a JSON value.
        data_type: boolean
      - name: is_focus_manage
        description:
          Boolean — whether the field is managed by Focus rather than locally.
        data_type: boolean
      - name: is_translate
        description: Boolean — whether the field is eligible for translation.
        data_type: boolean
      - name: is_column_adopted
        description: >-
          Boolean — whether the field has been adopted into a dedicated storage
          column.
        data_type: boolean
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__custom_fields --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `id` PASS. A contract mismatch
means a YAML `data_type` disagrees with the warehouse — the four `is_*` columns
must be `boolean`, `max_length`/`required`/`inactive`/`encrypted`/`district_id`
are `int`, the queries/text are `string`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance add \
  src/dbt/focus/models/staging/stg_focus__custom_fields.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_fields.yml
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance \
  commit -m "feat(dbt): add stg_focus__custom_fields (#4213)"
```

---

### Task 2: `stg_focus__custom_field_categories`

Narrow table — keep all non-audit / non-dlt columns. Has `deleted` -> filter +
omit. True `BOOL` columns: `focus_manage`, `state` -> `is_focus_manage`,
`is_state`. `inactive`, `system`, `sis`, `erp`, etc. are `INT64` 0/1 flags kept
raw; `archived` is a raw `STRING` kept as-is.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__custom_field_categories.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__custom_field_categories.yml`

**Interfaces:**

- Consumes: `source("focus", "custom_field_categories")`
- Produces: model `stg_focus__custom_field_categories`, grain one row per `id`
  (a custom field category). Referenced by
  `custom_fields_join_categories.category_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    title,
    source_class,
    form,
    color,
    icon,
    sort_order,
    inactive,
    legacy_id,
    form_template,
    default_profiles_view,
    default_profiles_edit,
    sis,
    erp,
    completion_email_recipient,
    email_validation,
    header_background,
    header_image_id,
    district_id,
    system,
    alias,
    settings,
    application_editor_generated,
    virtual,
    short_name,
    archived,
    created_at,
    updated_at,
    focus_manage as is_focus_manage,
    state as is_state,
from {{ source("focus", "custom_field_categories") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__custom_field_categories
    description: >-
      Focus custom field categories — one row per category grouping custom
      fields on a profile or form. Live rows only (soft-deleted rows filtered
      out).
    columns:
      - name: id
        description: Primary key — Focus custom field category id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Full category name.
        data_type: string
      - name: source_class
        description: Owning entity class for the category.
        data_type: string
      - name: form
        description: Flag (0/1) — whether the category is a form.
        data_type: int
      - name: color
        description: UI display color for the category.
        data_type: string
      - name: icon
        description: UI icon identifier for the category.
        data_type: string
      - name: sort_order
        description: Display sort order within the category list.
        data_type: int
      - name: inactive
        description: >-
          Raw inactive flag (0/1) — a category attribute, NOT a soft-delete
          sentinel.
        data_type: int
      - name: legacy_id
        description: Legacy Focus category id carried over from migration.
        data_type: int
      - name: form_template
        description: Form template id associated with the category.
        data_type: int
      - name: default_profiles_view
        description: Default profile-view permission level for the category.
        data_type: string
      - name: default_profiles_edit
        description: Default profile-edit permission level for the category.
        data_type: string
      - name: sis
        description: Flag (0/1) — whether the category is a SIS category.
        data_type: int
      - name: erp
        description: Flag (0/1) — whether the category is an ERP category.
        data_type: int
      - name: completion_email_recipient
        description: Email recipient notified on category form completion.
        data_type: string
      - name: email_validation
        description: Flag (0/1) — whether email validation is enabled.
        data_type: int
      - name: header_background
        description: Header background style for the category form.
        data_type: string
      - name: header_image_id
        description: Header image id for the category form.
        data_type: int
      - name: district_id
        description: Focus district id the category is scoped to.
        data_type: int
      - name: system
        description: Flag (0/1) — whether the category is a system category.
        data_type: int
      - name: alias
        description: Focus category alias.
        data_type: string
      - name: settings
        description: Serialized category settings blob.
        data_type: string
      - name: application_editor_generated
        description:
          Flag (0/1) — whether the category was generated by the application
          editor.
        data_type: int
      - name: virtual
        description: Flag (0/1) — whether the category is virtual.
        data_type: int
      - name: short_name
        description: Abbreviated category label.
        data_type: string
      - name: archived
        description: >-
          Raw archived flag (string) — a category attribute, NOT a soft-delete
          sentinel.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
      - name: is_focus_manage
        description:
          Boolean — whether the category is managed by Focus rather than
          locally.
        data_type: boolean
      - name: is_state
        description:
          Boolean — whether the category is a state-reporting category.
        data_type: boolean
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__custom_field_categories --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. `is_focus_manage` /
`is_state` must be `boolean`; `archived` is `string`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance add \
  src/dbt/focus/models/staging/stg_focus__custom_field_categories.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_categories.yml
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance \
  commit -m "feat(dbt): add stg_focus__custom_field_categories (#4213)"
```

---

### Task 3: `stg_focus__custom_field_select_options`

The decode lookup — `code` -> `label` for `select`/`multiple` custom fields,
keyed by `source_class` + `source_id` (the owning `custom_fields.id`). Keep all
non-audit / non-dlt columns. Has `deleted` -> filter + omit. No `BOOL` columns.
`inactive` / `migrated` are `INT64` flags kept raw. `sort_order` is `NUMERIC`.

**Files:**

- Create:
  `src/dbt/focus/models/staging/stg_focus__custom_field_select_options.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__custom_field_select_options.yml`

**Interfaces:**

- Consumes: `source("focus", "custom_field_select_options")`
- Produces: model `stg_focus__custom_field_select_options`, grain one row per
  `id`. Wave 2 decode joins `source_id` -> `stg_focus__custom_fields.id` and
  maps stored `code` -> display `label`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    source_class,
    source_id,
    code,
    label,
    sort_order,
    min_syear,
    max_syear,
    inactive,
    migrated,
    district_id,
    parent_student_label,
    created_at,
    updated_at,
from {{ source("focus", "custom_field_select_options") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__custom_field_select_options
    description: >-
      Focus select option definitions — one row per option for a select or
      multiple custom field. The code -> label decode lookup keyed by
      source_class and source_id (the owning custom field id). Live rows only
      (soft-deleted rows filtered out).
    columns:
      - name: id
        description: Primary key — Focus select option id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: source_class
        description: Owning entity class for the option's field.
        data_type: string
      - name: source_id
        description: >-
          Owning custom field id — joins to stg_focus__custom_fields.id for the
          decode follow-up.
        data_type: int
      - name: code
        description: Stored code value persisted on the entity record.
        data_type: string
      - name: label
        description: Human-readable label displayed for the code.
        data_type: string
      - name: sort_order
        description: Display sort order within the option list.
        data_type: numeric
      - name: min_syear
        description: Earliest school year the option is valid for.
        data_type: int
      - name: max_syear
        description: Latest school year the option is valid for.
        data_type: int
      - name: inactive
        description: >-
          Raw inactive flag (0/1) — an option attribute, NOT a soft-delete
          sentinel.
        data_type: int
      - name: migrated
        description:
          Flag (0/1) — whether the option was migrated from a prior system.
        data_type: int
      - name: district_id
        description: Focus district id the option is scoped to.
        data_type: int
      - name: parent_student_label
        description: Alternate label shown in the parent/student portal context.
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
`uv run dbt build --select stg_focus__custom_field_select_options --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. `sort_order` must be
`numeric` (not `int`/`float64`) to satisfy the contract.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance add \
  src/dbt/focus/models/staging/stg_focus__custom_field_select_options.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_select_options.yml
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance \
  commit -m "feat(dbt): add stg_focus__custom_field_select_options (#4213)"
```

---

### Task 4: `stg_focus__custom_field_log_columns`

Defines the columns of a log-type custom field — maps each `log_fieldN` slot in
`custom_field_log_entries` to a column definition (title, type, option query).
Keep all non-audit / non-dlt columns. Has `deleted` -> filter + omit. True
`BOOL` columns: `translate`, `visible_on_summary` -> `is_translate`,
`is_visible_on_summary`. `fixed`, `required`, `inactive`, `system`, etc. are
`INT64` flags kept raw.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__custom_field_log_columns.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__custom_field_log_columns.yml`

**Interfaces:**

- Consumes: `source("focus", "custom_field_log_columns")`
- Produces: model `stg_focus__custom_field_log_columns`, grain one row per `id`.
  Wave 2 log reshape joins `field_id` -> the log field and orders by
  `sort_order` to label the `log_fieldN` slots.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    field_id,
    column_name,
    type,
    title,
    description,
    default_value,
    fallback_value,
    max_length,
    total,
    primary_sort,
    secondary_sort,
    option_query,
    computed_query,
    sort_order,
    new_record,
    rich_text,
    fixed,
    required,
    inactive,
    system,
    imported,
    suggestion_query,
    restricted,
    help_url,
    academic_record_category,
    file_retention,
    min_width,
    max_width,
    alias,
    settings,
    notes,
    created_at,
    updated_at,
    translate as is_translate,
    visible_on_summary as is_visible_on_summary,
from {{ source("focus", "custom_field_log_columns") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__custom_field_log_columns
    description: >-
      Focus log-field column definitions — one row per column within a log-type
      custom field, mapping a log_fieldN slot to its title, type, and option
      query. Powers the deferred log-entry reshape. Live rows only (soft-deleted
      rows filtered out).
    columns:
      - name: id
        description: Primary key — Focus log column id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: field_id
        description: >-
          Owning log custom field id — joins to stg_focus__custom_fields.id and
          groups the log columns for a field.
        data_type: int
      - name: column_name
        description: Underlying storage column name (the log_fieldN slot).
        data_type: string
      - name: type
        description: Log column input type (e.g. select, text, date, numeric).
        data_type: string
      - name: title
        description: Human-readable log column label.
        data_type: string
      - name: description
        description: Long-form description of the log column.
        data_type: string
      - name: default_value
        description: Default value applied when no value is entered.
        data_type: string
      - name: fallback_value
        description: Fallback value used when the stored value is empty.
        data_type: string
      - name: max_length
        description: Maximum character length allowed for the value.
        data_type: int
      - name: total
        description: Flag (0/1) — whether the column is totaled.
        data_type: int
      - name: primary_sort
        description: Primary sort precedence for the column.
        data_type: int
      - name: secondary_sort
        description: Secondary sort precedence for the column.
        data_type: int
      - name: option_query
        description: Query backing the select option list for the column.
        data_type: string
      - name: computed_query
        description: Query used to compute the column value.
        data_type: string
      - name: sort_order
        description: >-
          Display sort order — orders the log_fieldN slots within the field for
          the reshape.
        data_type: int
      - name: new_record
        description:
          Flag (0/1) — whether the column appears on new-record entry.
        data_type: int
      - name: rich_text
        description: Flag (0/1) — whether the column uses rich text.
        data_type: int
      - name: fixed
        description: Flag (0/1) — whether the column is fixed (non-removable).
        data_type: int
      - name: required
        description: Flag (0/1) — whether the column is required on entry.
        data_type: int
      - name: inactive
        description: >-
          Raw inactive flag (0/1) — a column attribute, NOT a soft-delete
          sentinel.
        data_type: int
      - name: system
        description: Flag (0/1) — whether the column is a system column.
        data_type: int
      - name: imported
        description: Flag (0/1) — whether the column was imported.
        data_type: int
      - name: suggestion_query
        description: Query backing value suggestions for the column.
        data_type: string
      - name: restricted
        description: Flag (0/1) — whether access to the column is restricted.
        data_type: int
      - name: help_url
        description: Help URL associated with the column.
        data_type: string
      - name: academic_record_category
        description: Academic record category the column maps to.
        data_type: string
      - name: file_retention
        description: File retention setting (0/1) for file-type columns.
        data_type: int
      - name: min_width
        description: Minimum display width for the column.
        data_type: string
      - name: max_width
        description: Maximum display width for the column.
        data_type: string
      - name: alias
        description: Focus log column alias.
        data_type: string
      - name: settings
        description: Serialized column settings blob.
        data_type: string
      - name: notes
        description: Free-text notes on the column.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
      - name: is_translate
        description: Boolean — whether the column is eligible for translation.
        data_type: boolean
      - name: is_visible_on_summary
        description: Boolean — whether the column is shown on the summary view.
        data_type: boolean
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__custom_field_log_columns --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. `is_translate` /
`is_visible_on_summary` must be `boolean`; `total`/`primary_sort`/`fixed` etc.
are `int`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance add \
  src/dbt/focus/models/staging/stg_focus__custom_field_log_columns.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_log_columns.yml
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance \
  commit -m "feat(dbt): add stg_focus__custom_field_log_columns (#4213)"
```

---

### Task 5: `stg_focus__custom_field_log_entries`

The log value table — one row per log entry, with 30 generic `log_field1..30`
slots whose meaning is defined by `custom_field_log_columns` for the entry's
`field_id`. Curated to the reshape-relevant set per the batch facts. NO
`deleted` column on this table — NO soft-delete filter. No `BOOL` columns.
`imported` is `STRING` here (kept raw). `school_id`, `source_id`, `field_id`,
`form_record_id`, `syear` are `INT64`.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__custom_field_log_entries.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__custom_field_log_entries.yml`

**Interfaces:**

- Consumes: `source("focus", "custom_field_log_entries")`
- Produces: model `stg_focus__custom_field_log_entries`, grain one row per `id`.
  Wave 2 reshape unpivots `log_field1..log_field30` and labels each slot via
  `stg_focus__custom_field_log_columns` joined on `field_id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    school_id,
    source_class,
    source_id,
    field_id,
    form_record_id,
    syear,
    log_field1,
    log_field2,
    log_field3,
    log_field4,
    log_field5,
    log_field6,
    log_field7,
    log_field8,
    log_field9,
    log_field10,
    log_field11,
    log_field12,
    log_field13,
    log_field14,
    log_field15,
    log_field16,
    log_field17,
    log_field18,
    log_field19,
    log_field20,
    log_field21,
    log_field22,
    log_field23,
    log_field24,
    log_field25,
    log_field26,
    log_field27,
    log_field28,
    log_field29,
    log_field30,
    completed_at,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "custom_field_log_entries") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__custom_field_log_entries
    description: >-
      Focus custom field log entries — one row per log entry against an entity
      record. The 30 generic log_field slots carry the stored values; their
      meaning is defined per field by stg_focus__custom_field_log_columns. This
      table has no soft-delete column, so no rows are filtered. Powers the
      deferred log-entry reshape.
    columns:
      - name: id
        description: Primary key — Focus log entry id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: school_id
        description: Focus school id the log entry belongs to.
        data_type: int
      - name: source_class
        description: Owning entity class for the log entry.
        data_type: string
      - name: source_id
        description: Owning entity record id the log entry is attached to.
        data_type: int
      - name: field_id
        description: >-
          Owning log custom field id — joins to
          stg_focus__custom_field_log_columns.field_id to label the slots.
        data_type: int
      - name: form_record_id
        description: Form record id grouping the log entry.
        data_type: int
      - name: syear
        description: Focus school year (start year, e.g. 2025 = 2025-26).
        data_type: int
      - name: log_field1
        description:
          Generic log value slot 1 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field2
        description:
          Generic log value slot 2 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field3
        description:
          Generic log value slot 3 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field4
        description:
          Generic log value slot 4 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field5
        description:
          Generic log value slot 5 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field6
        description:
          Generic log value slot 6 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field7
        description:
          Generic log value slot 7 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field8
        description:
          Generic log value slot 8 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field9
        description:
          Generic log value slot 9 — meaning defined by the field's log columns.
        data_type: string
      - name: log_field10
        description:
          Generic log value slot 10 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field11
        description:
          Generic log value slot 11 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field12
        description:
          Generic log value slot 12 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field13
        description:
          Generic log value slot 13 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field14
        description:
          Generic log value slot 14 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field15
        description:
          Generic log value slot 15 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field16
        description:
          Generic log value slot 16 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field17
        description:
          Generic log value slot 17 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field18
        description:
          Generic log value slot 18 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field19
        description:
          Generic log value slot 19 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field20
        description:
          Generic log value slot 20 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field21
        description:
          Generic log value slot 21 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field22
        description:
          Generic log value slot 22 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field23
        description:
          Generic log value slot 23 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field24
        description:
          Generic log value slot 24 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field25
        description:
          Generic log value slot 25 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field26
        description:
          Generic log value slot 26 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field27
        description:
          Generic log value slot 27 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field28
        description:
          Generic log value slot 28 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field29
        description:
          Generic log value slot 29 — meaning defined by the field's log
          columns.
        data_type: string
      - name: log_field30
        description:
          Generic log value slot 30 — meaning defined by the field's log
          columns.
        data_type: string
      - name: completed_at
        description: Timestamp the log entry was completed.
        data_type: timestamp
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
`uv run dbt build --select stg_focus__custom_field_log_entries --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. All 30 `log_fieldN` are
`string`; there is NO `deleted` column so the SQL has NO `where` clause.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance add \
  src/dbt/focus/models/staging/stg_focus__custom_field_log_entries.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_log_entries.yml
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance \
  commit -m "feat(dbt): add stg_focus__custom_field_log_entries (#4213)"
```

---

### Task 6: `stg_focus__custom_fields_join_categories`

The field-to-category bridge — one row per (field, category) assignment. Keep
all non-audit / non-dlt columns. Has `deleted` -> filter + omit. No `BOOL`
columns. `imported` is `INT64` here (kept raw). PK is `id` (NOT the
field_id/category_id composite) per the batch facts.

**Files:**

- Create:
  `src/dbt/focus/models/staging/stg_focus__custom_fields_join_categories.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__custom_fields_join_categories.yml`

**Interfaces:**

- Consumes: `source("focus", "custom_fields_join_categories")`
- Produces: model `stg_focus__custom_fields_join_categories`, grain one row per
  `id`. Bridges `field_id` -> `stg_focus__custom_fields.id` and `category_id` ->
  `stg_focus__custom_field_categories.id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    field_id,
    category_id,
    sort_order,
    imported,
    field_class,
    district_id,
    created_at,
    updated_at,
from {{ source("focus", "custom_fields_join_categories") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__custom_fields_join_categories
    description: >-
      Focus custom field to category assignments — one row per (field, category)
      pairing. Bridges custom fields to the categories they appear under. Live
      rows only (soft-deleted rows filtered out).
    columns:
      - name: id
        description: Primary key — Focus field-category assignment id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: field_id
        description: >-
          Custom field id — joins to stg_focus__custom_fields.id.
        data_type: int
      - name: category_id
        description: >-
          Custom field category id — joins to
          stg_focus__custom_field_categories.id.
        data_type: int
      - name: sort_order
        description: Display sort order of the field within the category.
        data_type: int
      - name: imported
        description: Flag (0/1) — whether the assignment was imported.
        data_type: int
      - name: field_class
        description: Entity class of the field in the assignment.
        data_type: string
      - name: district_id
        description: Focus district id the assignment is scoped to.
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
`uv run dbt build --select stg_focus__custom_fields_join_categories --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance add \
  src/dbt/focus/models/staging/stg_focus__custom_fields_join_categories.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_fields_join_categories.yml
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance \
  commit -m "feat(dbt): add stg_focus__custom_fields_join_categories (#4213)"
```

---

## Final verification

- [ ] **Build all six together:**

```bash
uv run dbt build \
  --select stg_focus__custom_fields stg_focus__custom_field_categories \
  stg_focus__custom_field_select_options stg_focus__custom_field_log_columns \
  stg_focus__custom_field_log_entries stg_focus__custom_fields_join_categories \
  --project-dir src/dbt/kippmiami
```

Expected: 6 models build, 12 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook). Run from inside the worktree
      (`/workspaces/teamster/.worktrees/cbini-feat-focus-staging-attendance`):

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__custom_fields.sql \
  src/dbt/focus/models/staging/stg_focus__custom_field_categories.sql \
  src/dbt/focus/models/staging/stg_focus__custom_field_select_options.sql \
  src/dbt/focus/models/staging/stg_focus__custom_field_log_columns.sql \
  src/dbt/focus/models/staging/stg_focus__custom_field_log_entries.sql \
  src/dbt/focus/models/staging/stg_focus__custom_fields_join_categories.sql \
  src/dbt/focus/models/staging/properties/stg_focus__custom_fields.yml \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_categories.yml \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_select_options.yml \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_log_columns.yml \
  src/dbt/focus/models/staging/properties/stg_focus__custom_field_log_entries.yml \
  src/dbt/focus/models/staging/properties/stg_focus__custom_fields_join_categories.yml
```

Expected: no findings. The likely flags are AL09 (a self-alias — none here since
every `is_*` rename changes the name) and ST06 (column order — plain refs then
the `is_*` renames, which is the order written).

## Out of scope (other plans / issues)

- **Wave 2 decode follow-up** — decoding the encoded `select`/`multiple` custom
  values via `stg_focus__custom_field_select_options`, and reshaping the
  `log_field1..30` slots from `stg_focus__custom_field_log_entries` using
  `stg_focus__custom_field_log_columns`. This batch only stages the metadata
  cleanly; the decode/reshape is deferred (#4213 Wave 2).
- **Custom value unpivot** — custom values are inline-aliased within their
  entity batches (A students, B enrollment, D courses, G users), not here.
- **kipptaf region source + `stg_kippmiami__focus__*` wrappers** — deferred to
  the kipptaf-integration plan (Wave 3); add a wrapper only when a mart consumes
  one of these.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all six custom-field metadata tables have a staging task
   (Tasks 1-6). ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command + exact commit command. No TBD/TODO/"similar to". ✓
3. **PK tests:** every model has `unique` + `not_null` on `id` at
   `config: severity: error`. ✓
4. **Soft-delete:** `where deleted is null` + `deleted` omitted on Tasks 1, 2,
   3, 4, 6; Task 5 (`custom_field_log_entries`) has no `deleted` column and no
   filter. ✓
5. **BOOL `is_` renames:** `custom_fields` (json/focus_manage/translate/
   column_adopted), `custom_field_categories` (focus_manage/state),
   `custom_field_log_columns` (translate/visible_on_summary) — declared
   `boolean` in YAML, renamed in SQL. `inactive`/`required`/`encrypted`/etc.
   (INT64) and `archived`/`imported` (STRING) kept raw. ✓
6. **Audit/dlt exclusion:** no `created_by_class`/`_id`,
   `updated_by_class`/`_id`, or `_dlt_*` in any projection. `created_at` /
   `updated_at` / `uuid` (where present) kept. ✓
7. **Type consistency:** YAML `data_type` matches the warehouse type from
   `INFORMATION_SCHEMA.COLUMNS` — note `custom_field_select_options.sort_order`
   is `numeric` (not `int`); `custom_field_log_entries.imported` is `string`
   (and dropped — not in the curated set);
   `custom_fields_join_categories. imported` is `int`. ✓
8. **ST06 / AL09:** plain refs then the `is_*` renames in source order; every
   rename changes the output name so no AL09 self-alias. ✓
