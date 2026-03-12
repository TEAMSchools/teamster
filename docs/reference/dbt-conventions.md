# dbt Conventions

## Model conventions

Models follow standard prefixes reflecting their layer in the data flow.

### Staging (`stg_`)

Modular building blocks from source data.

- File naming: `stg_{source}__{entity}.sql`
- **`contract: enforced: true`** — required on all staging models
- **Uniqueness test** — required: either a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for composite keys

### Intermediate (`int_`)

Layers of logic with clear and specific purposes, preparing staging models to
join into the entities we want.

- Folder structure: subdirectories by area of business concern
- File naming: `int_{business_concern}__{entity}_{verb}.sql`
  - Business concerns: `assessments`, `surveys`, `people`
  - Verbs: `pivot`, `unpivot`, `rollup`
- **Uniqueness test** — required: either a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for composite keys

### Marts / Extracts (`rpt_`)

Wide, rich views of the entities our organization cares about, or extracts
consumed by reporting tools and applications.

- **`contract: enforced: true`** — required on all marts and extract models.
  These are the last stop before data reaches an external reporting tool
  (Tableau, PowerSchool, Google Sheets, etc.). Schema changes break downstream
  [exposures](https://docs.getdbt.com/reference/exposure-properties) and must be
  made deliberately.
- **Uniqueness test** — required: either a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for composite keys

## Exposures

Every external tool that consumes our data must have a
[dbt exposure](https://docs.getdbt.com/reference/exposure-properties) defined in
the consuming project (typically `src/dbt/kipptaf/models/exposures/`). Exposures
make the dependency graph explicit and power Dagster asset lineage.

**All exposures** require a `name`, `label`, `type`, `owner`, `depends_on`
(listing every model the tool uses), and a `url` linking to the external
tool/workbook/sheet:

```yaml
exposures:
  - name: exposure_name_snake_case
    label: Human Readable Title
    type: dashboard | application | analysis
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_tableau__some_model")
    url: https://...
    config:
      meta:
        dagster:
          kinds:
            - tableau # or: googlesheets, powerschool, etc.
```

**Tableau dashboards** that refresh on a schedule must additionally include the
Tableau workbook LSID and a `cron_schedule` under `asset.metadata`. Workbooks
without a scheduled refresh can omit the `asset` block:

```yaml
config:
  meta:
    dagster:
      kinds:
        - tableau
      asset:
        metadata:
          id: <tableau-workbook-lsid-uuid>
          cron_schedule: "0 7 * * *" # omit entirely if no scheduled refresh
```
