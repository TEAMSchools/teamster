# dbt Conventions

This page is built from the rule files Claude reads
(`.claude/rules/dbt-architecture.md`, `.claude/rules/dbt-marts.md`, and
`.claude/rules/dbt-sql.md`), so people and Claude review against the same text.
Cite rules by ID (`A2`, `S10`) in review.

A rule changes through a PR to its rule file. If you disagree with a rule in
review, open an issue; the feature PR follows the current rule.

The standard applies to the lines a PR adds or changes. Old violations elsewhere
in a model are left alone, and existing models are not swept.

--8<-- ".claude/rules/dbt-architecture.md:architecture"

--8<-- ".claude/rules/dbt-marts.md:marts"

--8<-- ".claude/rules/dbt-sql.md:sql-style"

## Reference

### Required config per layer

- `stg_`, marts, and `rpt_` models set `contract: enforced: true`. Marts and
  `rpt_` models are the last stop before data reaches an external tool (Tableau,
  PowerSchool, Google Sheets), so a schema change breaks downstream
  [exposures](https://docs.getdbt.com/reference/exposure-properties) and must be
  deliberate.
- Every model has a uniqueness test: a single-column `unique:` test or
  `dbt_utils.unique_combination_of_columns` for a composite key.

### Region labels

A10 covers joining unioned regional models on `_dbt_source_project`. Each union
view materializes that column once; see `src/dbt/kipptaf/CLAUDE.md` for which
form applies. For a human-readable region label, use the `extract_region()`
macro:

```sql
{{ extract_region("s") }} as region
```

### Handy SQL

- Timezone-aware today, so `current_date` reflects local time rather than UTC:

  ```sql
  current_date('{{ var("local_timezone") }}')
  ```

- Removing diacritical marks, to normalize names with accented characters:

  ```sql
  regexp_replace(normalize(name_col, NFD), r'\pM', '')
  ```

- Time travel, to query a table as it existed at a point in time:

  ```sql
  select *
  from my_table
  for system_time as of timestamp('2025-08-22 23:59:59')
  ```

- New or modified external sources must be staged before building. See
  [Staging external sources](../guides/dbt-development.md#staging-external-sources)
  for the full command and CI requirements.

### `ref()` and `source()`

Use `ref()` to reference other dbt models; use `source()` for raw source tables
declared in a `sources:` YAML file:

```sql
{{ ref("stg_amplify__benchmark_student_summary") }}
{{ source("amplify", "src_amplify__benchmark_student_summary") }}
```

### BigQuery scalar functions

Shared UDFs in the `functions` dataset:

| Function                            | Returns                       |
| ----------------------------------- | ----------------------------- |
| `functions.current_academic_year()` | Current academic year integer |
| `functions.date_to_sy(date_col)`    | Academic year of a given date |

```sql
select
    functions.current_academic_year() as academic_year,
    functions.date_to_sy(att_date) as att_academic_year,
from my_table
```

`functions.region_join` also exists in the dataset. Don't use it; join on
`_dbt_source_project` (A10).

### Model properties file

Every model must have a corresponding `[model_name].yml` properties file. Write
it by hand — there is no scaffold generator in this repo. Column names and types
come from `INFORMATION_SCHEMA.COLUMNS` on the built relation:

```sql
select column_name, data_type
from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
where table_name = '<model_name>'
order by ordinal_position
```

The shape:

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
```

### Exposures

Every external tool that consumes our data must have a
[dbt exposure](https://docs.getdbt.com/reference/exposure-properties) defined in
the consuming project (typically `src/dbt/kipptaf/models/exposures/`). Exposures
make the dependency graph explicit and power Dagster asset lineage.

All exposures require a `name`, `label`, `type`, `owner`, `depends_on` (listing
every model the tool uses), and a `url` linking to the external
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

Tableau dashboards that refresh on a schedule must also include the Tableau
workbook LSID and a `cron_schedule` under `asset.metadata`. Workbooks without a
scheduled refresh can omit the `asset` block:

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
