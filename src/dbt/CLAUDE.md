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
      - unique

# multi-column uniqueness (when no single column is unique)
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - column_a
          - column_b
```

### Test config defaults

All kipp\* `dbt_project.yml` files set project-level test defaults:

```yaml
data_tests:
  +severity: warn
  +store_failures: true
  +store_failures_as: view
```

- Do not add `store_failures: true` to individual tests — the project default
  handles it
- Tests that must error (not warn) need explicit `config: severity: error`
- Unscoped `+config` applies to tests from all installed packages, not just the
  current project

### VS Code YAML schema

The VS Code YAML extension does not recognize `store_failures_as` — the
resulting diagnostic is a false positive. dbt parses it correctly.

### SQL conventions

- **Soft-delete filters**: Apply in the **staging model**, not in downstream
  `ON` clauses. Deleted rows should never reach intermediate or mart models.
  Omit columns whose value is predetermined by the WHERE filter (e.g.,
  `deleted_at` after `WHERE deleted_at IS NULL`) — they add no signal.
- **No `GROUP BY` without aggregation** — use `DISTINCT` instead (see next rule
  for deduplication constraints).
- **No manual deduplication** — do not use `SELECT DISTINCT` or
  `qualify row_number() over (...) = 1` for deduplication. Use
  `dbt_utils.deduplicate()` with an explicit `partition_by` and `order_by`. If
  `DISTINCT` is truly unavoidable, it must include a `-- TODO:` comment
  explaining why and what needs to be fixed upstream.
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

### YAML conventions

- All new or modified models require `description:` on the model and every
  column. Profile staging data via BigQuery MCP; infer downstream from parents.
  Describe calculated fields by logic. Use qualitative language — no stats.
- Columns with `data_tests:` should be sorted to the top of the `columns:` list
  for visibility.
- Column renames for semantic clarity (e.g., boolean prefixing with `is_`,
  reserved word aliases) belong in the staging model, not downstream.

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

## Package Macro Resolution

Source-system projects are consumed as dbt packages by school projects. dbt
ignores `generate_schema_name` overrides in installed packages — it must live in
the consuming project. Custom macros (e.g., `resolve_source_schema`) ARE
resolved from the consuming project's namespace when called from package source
files.

## Profiles Architecture

Two `profiles.yml` files per school/network project:

- **`.dbt/profiles.yml`** — local dev + dbt Cloud, multiple targets
  (`dev`/`staging`/`prod`)
- **`src/dbt/<project>/profiles.yml`** — shipped with code, used by Dagster

Source-system projects only appear in `.dbt/profiles.yml` (not shipped to
Dagster — they run as packages inside school projects).
