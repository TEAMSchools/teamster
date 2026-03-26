# CLAUDE.md — `src/dbt/`

## Overview

Fifteen dbt projects organized into three tiers:

| Tier                  | Projects                                                                                                           | Purpose                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| **Source-system**     | `amplify`, `deanslist`, `edplan`, `finalsite`, `iready`, `overgrad`, `pearson`, `powerschool`, `renlearn`, `titan` | Clean and contract-enforce raw data from one source system    |
| **District-specific** | `kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`                                                            | Combine source packages for a single district                 |
| **Network analytics** | `kipptaf`                                                                                                          | Cross-district marts, reporting, and extracts for the network |

Data flows **source → district → kipptaf**: source-system projects are consumed
as local dbt packages by district projects, which are in turn sourced by
`kipptaf`.

## Project Dependency Map

```text
amplify ──────┐
deanslist ────┤
edplan ───────┤
finalsite ────┤                ┌─ kippnewark ──┐
iready ───────┼── (packages) ─┼─ kippcamden ───┼── (sources) ── kipptaf
overgrad ─────┤                ├─ kippmiami ───┤
pearson ──────┤                └─ kipppaterson ─┘
powerschool ──┤
renlearn ─────┤
titan ────────┘
```

Not every district uses every source package. See each district project's
CLAUDE.md for its active packages.

## Shared Dependencies

All projects use:

- `dbt-labs/dbt_utils` — `unique_combination_of_columns`,
  `generate_surrogate_key`, etc.
- `dbt-labs/dbt_external_tables` — BigQuery external table staging

District and network projects additionally use `dbt-labs/codegen`.

## Variable Override Pattern

Source-system projects declare variables with null/zero defaults
(`bigquery_external_connection_name: null`, `current_academic_year: 0`, etc.).
Consuming district projects override these in their own `dbt_project.yml`. This
allows the same source project code to work across multiple district
deployments.

## External Table Pattern

All staging sources use BigQuery external tables backed by GCS (Avro format,
BigLake connection, 7-day staleness window). Each source's `sources.yml`
includes `dagster: asset_key` metadata so Dagster can track lineage.

## Model Conventions

These conventions apply to **every** dbt project in this directory. Per-project
CLAUDE.md files reference this section rather than repeating it.

### Per-layer requirements

**All staging models must**:

1. Have `contract: enforced: true` (set at directory level in `dbt_project.yml`)
2. Have a uniqueness test — either `unique:` on a single column or
   `dbt_utils.unique_combination_of_columns`

**All intermediate models must**:

1. Have a uniqueness test
2. Not be consumed directly by external tools or reports — a reporting view
   (`rpt_*`) must always sit between an intermediate model and an external
   consumer, buffering external dependencies from internal schema evolution

**All `rpt_`, `dim_*`, and `fct_*` models must**:

1. Have `contract: enforced: true`
2. Have a uniqueness test

### Uniqueness test examples

```yaml
# single-column uniqueness
columns:
  - name: surrogate_key
    data_tests:
      - unique:
          config:
            store_failures: true

# multi-column uniqueness (when no single column is unique)
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - column_a
          - column_b
      config:
        store_failures: true
```

### SQL conventions

- **Soft-delete filters**: Apply in the **staging model**, not in downstream
  `ON` clauses. Deleted rows should never reach intermediate or mart models.
- **No `GROUP BY` without aggregation** — use `DISTINCT` instead (see next rule
  for deduplication constraints).
- **No `SELECT DISTINCT` for deduplication** — use `dbt_utils.deduplicate()`
  with an explicit `partition_by` and `order_by`. If `DISTINCT` is truly
  unavoidable, it must include a `-- TODO:` comment explaining why and what
  needs to be fixed upstream.
- **No `GROUP BY ALL`** — list grouping columns explicitly. `GROUP BY ALL`
  breaks silently when upstream columns change.
- **No `ORDER BY`** — ordering belongs in the reporting layer, not dbt models.
- **No `SELECT *` in final `SELECT` of `rpt_`/mart models** — list columns
  explicitly. Pass-through CTEs (`select * from ref(...)`) are fine. Get the
  authoritative column list via `INFORMATION_SCHEMA.COLUMNS`:

  ```sql
  select column_name
  from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
  where table_name = '<model_name>'
  order by ordinal_position
  ```

- **`ON` vs `WHERE`** — row filters on the preserved table belong in `WHERE`,
  not `ON`. For `LEFT JOIN`, a filter in `ON` preserves non-matching rows.
  Exception: `FULL JOIN` conditions referencing one side stay in `ON`.
- **Timezone-aware today**:

  ```sql
  current_date('{{ var("local_timezone") }}')
  ```

### SQL column ordering in SELECT clauses (enforced by ST06)

Columns within a SELECT **must** follow this order — no interleaving:

1. Column enumerations (plain refs), grouped by source table in join order,
   separated by a blank line between each table's group
2. Constants and literals
3. Simple functions (`coalesce(...)`, simple `if(...)`)
4. Nested functions
5. Logicals (`if(condition, true, false)`)
6. Case statements
7. Window functions (`row_number() over (...)`)

When a SELECT reads from a single table/CTE, do not prefix columns with the
alias.

### Documentation

Column-level documentation belongs in the model's properties YAML as a
`description:` field, not as inline SQL comments.

### Legacy `base_` prefix

Existing `base_` models are being renamed to `int_`
([#2541](https://github.com/TEAMSchools/teamster/issues/2541)). Do not create
new `base_` models.

## SQL Style

All SQL follows `.trunk/config/.sqlfluff`. Key enforced rules:

- **Dialect**: BigQuery
- **Trailing commas**: required in `SELECT` clauses
- **Reserved words**: BigQuery reserved words as column names must be
  backtick-quoted in SQL and have `quote: true` in properties YAML
- **String literals**: single quotes only (no double quotes)
- **Line length**: 88 characters max

Do not flag code that follows these rules.
