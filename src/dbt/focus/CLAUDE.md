# CLAUDE.md — `dbt/focus/`

Source-system staging project for **Focus SIS** data (PostgreSQL). Provides the
BigQuery source definitions for Focus dlt loads, consumed by district-specific
dbt projects (currently `kippmiami`).

## Data Flow

Focus Postgres → dlt `sql_database` → BigQuery (`dagster_<project>_dlt_focus`) →
dbt staging models → dbt intermediate models

## Focus field value codes

A Focus custom field's allowed value codes live in
`dagster_<district>_dlt_focus.custom_fields` (find the field by `title` /
`column_name`) joined to `custom_field_select_options` on
`custom_field_select_options.source_id = custom_fields.id` — `code` is the value
Focus expects, `label` is the human name. The join is `source_id` only — also
filter `custom_field_select_options.source_class = 'CustomField'` (or
`'CustomFieldLogColumn'` for log-column slots) so the shared `source_id` space
doesn't collide across owner types. `source_class` on the options table is the
owner-type literal, never the entity class (`SISSchool`, etc.); matching the
entity class returns zero rows. To DECODE a stored value: the entity stores the
select-option `id` (`custom_field_select_options.id`) for some fields and the
`code` (e.g. `prior_state`=`FL`) for others, so match the stored value against
BOTH `id` and `code`, then read `label`. Verify by spot-checking decoded values
— a wrong match key returns all-null labels but still passes build, grain, and
lint. (`code` also drives Finalsite→Focus import crosswalks.)

**Custom-field storage.** Values live inline on the entity table's wide
`custom_NNN` columns (e.g. `students.custom_100000105`), NOT in `custom_fields`
— that is the _definition_ catalog. Join definition→entity column on
`custom_fields.column_name` + `source_class`. `title` is the readable name (slug
it for the staging alias); `select`/`multiple` values are stored option `id`s or
`code`s (varies by field; decode to `label` via the crosswalk above); `log`-type
values live in `custom_field_log_entries`; `computed`/`holder` are not stored.
Custom fields are NOT always named `custom_NNN` — some use semantic
`column_name`s (e.g. `users.birth_date`, `charter_*`); when profiling an
entity's populated custom fields, scan the FULL table and join the whole catalog
on `lower(column_name)`, since filtering to `custom_*`-prefixed columns silently
misses the semantic-named ones.

`source_class`→entity-table map (use the catalog's own spelling, NOT the
entity's): `SISStudent`→students, `FocusUser`→users, `SISSchool`→schools,
`StudentEnrollment`→student_enrollment, `CoursePeriod`→course_periods,
`CourseCatalog`→master_courses, `Course`→courses.

**Two join gotchas, each silently returns zero matches.** (1) `column_name` is
UPPERCASE in the catalog (`CUSTOM_FIELD_3`, `CUSTOM_2`) but lowercase on the
entity table (`custom_field_3`) — join on `lower(column_name)`. (2) Use the
catalog `source_class` spelling — e.g. enrollment fields are under
`StudentEnrollment`, not `SISStudentEnrollment`. With both handled, the
`course_periods`, `master_courses`, `courses`, and `student_enrollment`
positional `custom_N` / `custom_field_N` slots DO resolve to catalog titles
(e.g. `master_courses.custom_field_3` = "Core for Class Size",
`course_periods.custom_4` = "Scheduling Method"). Genuinely unlabeled (no
catalog row): `course_subjects` (no `CourseSubject` class) and
`master_courses.custom_field_11`.

## Source data conventions

**Soft-delete.** Focus `deleted INT64` is `NULL` for live rows and `1` for
deleted — **never `0`**. Filter `where deleted is null` in staging (`= 0`
matches nothing) and omit the column. Present on `students`, `users`, `schools`,
`address`, `student_enrollment_codes`, the `custom_field*` tables; absent on
others (e.g. `custom_field_log_entries`). `inactive`/`active`/`archived` are raw
attributes, not delete sentinels.

**Primary keys.** Most tables PK on `id`; some on `<entity>_id` (`address_id`,
`course_id`, `course_period_id`, `marking_period_id`, `period_id`,
students→`student_id`, users→`staff_id` (`profile_id` is null for nearly all
rows).

## Model Structure

```text
models/
  staging/
    sources-bigquery.yml          # BQ-native sources (dlt-loaded, not external)
    stg_focus__<table>.sql        # one contract-enforced model per source table
    properties/
      stg_focus__<table>.yml      # contract columns, tests, descriptions
```

Staging models are contract-enforced (`contract: enforced: true`, set at the
`staging` directory level in `dbt_project.yml`): every projected column is
declared with a `data_type` in `properties/`, with a `unique` + `not_null` PK
test at `severity: error`. Each model selects from a
`{{ source("focus", ...) }}` relation, drops dlt bookkeeping (`_dlt_*`) and the
audit-quad, and applies the soft-delete filter where the table has one. Data
comes from dlt (not external tables), so sources use `sources-bigquery.yml` with
a plain schema var. Intermediate (`int_focus__*`) models layer on top.

## Key Variables

| Variable                | Default                            | Notes                           |
| ----------------------- | ---------------------------------- | ------------------------------- |
| `focus_schema`          | `dagster_<project_name>_dlt_focus` | BQ dataset with dlt-loaded data |
| `current_academic_year` | `0`                                | Overridden per district         |
| `current_fiscal_year`   | `0`                                | Overridden per district         |
| `local_timezone`        | `UTC`                              | Overridden per district         |

## Cross-Project Usage

This project is never run standalone in production. District projects reference
it as a dbt package and override variables. `{{ project_name }}` in source
definitions resolves to the consuming district project name, enabling correct
Dagster asset key lineage.
