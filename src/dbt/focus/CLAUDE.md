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
Focus expects, `label` is the human name. Use this to build Finalsite→Focus
value crosswalks.

## Model Structure

```text
models/
  staging/
    sources-bigquery.yml   # BQ-native sources (dlt-loaded, not external tables)
```

Staging/intermediate SQL models are not yet implemented — only the source
definitions exist. When added, staging models will be contract-enforced
(`contract: enforced: true`, set at directory level in `dbt_project.yml`). Data
comes from dlt (not external tables), so sources use `sources-bigquery.yml` with
a plain schema var.

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
