# CLAUDE.md — `dbt/focus/`

Source-system staging project for **Focus SIS** data (PostgreSQL). Produces
clean, contract-enforced staging models consumed by district-specific dbt
projects (currently `kippmiami`).

## Data Flow

Focus Postgres → dlt `sql_database` → BigQuery (`dagster_<project>_dlt_focus`) →
dbt staging models → dbt intermediate models

## Model Structure

```text
models/
  staging/
    sources-bigquery.yml   # BQ-native sources (dlt-loaded, not external tables)
    stg_focus__*.sql       # one per source table
    properties/
      stg_focus__*.yml     # column contracts + tests
  intermediate/
    int_focus__*.sql       # domain-specific joins
    properties/
      int_focus__*.yml
```

All staging models have `contract: enforced: true`. Data comes from dlt (not
external tables), so sources use `sources-bigquery.yml` with a plain schema var.

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
