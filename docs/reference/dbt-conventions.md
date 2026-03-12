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

## SQL conventions

- **Use `union_dataset_join_clause()`** for any query that joins models using
  regional datasets.
- **No `GROUP BY` without aggregation** — use `DISTINCT` instead.
- **`DISTINCT` requires a comment** explaining why it is necessary.
- **No `ORDER BY` in `SELECT` statements** — ordering belongs in the reporting
  layer, not in dbt models.
- **No `GROUP BY ALL`** — never use in production models. Always list grouping
  columns explicitly; `GROUP BY ALL` obscures intent and breaks silently when
  upstream columns are added or removed.
- **No `SELECT *` in the final `SELECT` of `rpt_` or mart models** — list
  columns explicitly. Wildcards obscure column sourcing, create ambiguity when
  both sides of a join share a column name, and leave the contract declaration
  as the only readable spec. Pass-through CTEs (`select * from ref(...)`) are
  fine.
- **Filter conditions: `ON` vs `WHERE`** — row-filter conditions on the
  preserved table belong in `WHERE`, not `ON`. For `INNER JOIN` the result is
  identical but intent is hidden; for `LEFT JOIN`, a filter in `ON` keeps
  non-matching left rows whereas `WHERE` eliminates them — a silent semantic
  change. Exception: for `FULL JOIN`, conditions in `ON` that reference only one
  side are intentional and cannot be moved to `WHERE`.
- **New external sources** — before building, stage them first:

  ```bash
  uv run dbt run-operation stage_external_sources \
    --vars "{'ext_full_refresh': 'true'}" \
    --args 'select: [model_name]'
  ```

## Model properties file

Every model must have a corresponding `[model_name].yml` properties file.
Generate the scaffold with:

```bash
uv run dbt run-operation generate_model_yaml \
  --args '{"model_names": ["model_name"]}'
```

Then save the console output as the `.yml` file and fill it in:

```yaml
models:
  - name: model_name
    config:
      contract:
        enforced: false # keep false while building; remove this line before merging
    columns: # required for contracted models
      - name: column_name
        data_type: string | int64 | date | ... # required for contracted models
        data_tests: # optional column-level tests
          - not_null
          - accepted_values:
              values: [...]
    data_tests: # optional model-level tests
      - dbt_utils.unique_combination_of_columns: # use for composite keys
          arguments:
            combination_of_columns:
              - column_a
              - column_b
          config:
            store_failures: true
```

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
    type: dashboard | notebook | analysis | ml | application
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_tableau__some_model")
      - ref("another_model")
    url: https://... # optional
    config:
      meta:
        dagster:
          kinds:
            - tableau # or: googlesheets, powerschool, etc.
            - ... # additional kinds
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
