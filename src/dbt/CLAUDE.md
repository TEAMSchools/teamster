# CLAUDE.md — `src/dbt/`

## Overview

Fifteen dbt projects organized into three tiers:

| Tier                  | Projects                                                                                                           | Purpose                                                     |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| **Source-system**     | `amplify`, `deanslist`, `edplan`, `finalsite`, `iready`, `overgrad`, `pearson`, `powerschool`, `renlearn`, `titan` | Clean and contract-enforce raw data from one source system  |
| **School-specific**   | `kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`                                                            | Combine source packages for a single school network         |
| **Network analytics** | `kipptaf`                                                                                                          | Cross-school marts, reporting, and extracts for the network |

Data flows **source → school → kipptaf**: source-system projects are consumed as
local dbt packages by school projects, which are in turn sourced by `kipptaf`.

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

Not every school uses every source package. See each school project's CLAUDE.md
for its active packages.

## Shared Dependencies

All projects use:

- `dbt-labs/dbt_utils` — `unique_combination_of_columns`,
  `generate_surrogate_key`, etc.
- `dbt-labs/dbt_external_tables` — BigQuery external table staging

School and network projects additionally use `dbt-labs/codegen`.

## Variable Override Pattern

Source-system projects declare variables with null/zero defaults
(`bigquery_external_connection_name: null`, `current_academic_year: 0`, etc.).
Consuming school projects override these in their own `dbt_project.yml`. This
allows the same source project code to work across multiple school deployments.

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

### SQL antipatterns to avoid

- **Soft-delete filters**: Apply soft-delete exclusion filters in the **staging
  model** (`WHERE deleted_at IS NULL`, `WHERE NOT _fivetran_deleted`, etc.), not
  in intermediate JOIN `ON` clauses. Deleted rows should never reach downstream
  models.
- **`GROUP BY ALL`**: Always list grouping columns explicitly.
- **`SELECT *` in the final SELECT of `rpt_` or mart models**: Always list
  columns explicitly. Pass-through CTEs (`select * from ref(...)`) are fine.
- **`SELECT *` from models that use `dbt_utils.star()`**: See
  `src/dbt/kipptaf/CLAUDE.md` for the full guidance on selecting from
  star-generated models (includes `INFORMATION_SCHEMA.COLUMNS` query pattern).
- **`dbt_utils.get_relations_by_prefix`**: Do not use. It queries the BigQuery
  catalog at compile time to discover tables, which fails in dbt Cloud CI
  (`--defer`) because the PR schema is empty. Use `dbt_utils.union_relations`
  with explicit `ref()` calls instead.
- **Filter conditions in `ON` vs `WHERE`**: Row-filter conditions on the
  preserved table belong in `WHERE`, not `ON` (except `FULL JOIN`). For example,
  in `FROM a INNER JOIN b ON a.id = b.id AND b.deleted_at IS NULL`, the
  `b.deleted_at IS NULL` filter is on the joined table (`b`) and belongs in
  `ON`. A filter on the driving table (`a`) would belong in `WHERE`.

### SQL column ordering in SELECT clauses

Columns within a SELECT must follow this order:

1. Column enumerations (plain refs), grouped by source table in join order,
   separated by a blank line between each table's group
2. Simple functions (`coalesce(...)`, simple `if(...)`)
3. Nested functions
4. Logicals (`if(condition, true, false)`)
5. Case statements
6. Window functions (`row_number() over (...)`)

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
- **String literals**: single quotes only (no double quotes)
- **Line length**: 88 characters max

Do not flag code that follows these rules.

## Package Macro Resolution

Source-system projects are consumed as dbt packages by school projects. dbt
ignores `generate_schema_name` overrides in installed packages — it must live in
the consuming project. Custom macros (e.g., `resolve_source_schema`) ARE
resolved from the consuming project's namespace when called from package source
files.

Running `dbt parse` directly against a standalone source-system project will
fail if its source files call macros defined in consuming projects. This is
expected — source-system projects are only compiled as packages.

`stage_external_sources --args 'select: *'` stages all external sources;
`--args 'select: source_name'` scopes to one source.

## dbt Cloud

- **"Target name" in job settings** controls `target.name` in Jinja exactly —
  `"default"` is a literal string, not a placeholder. Set explicitly to
  `"staging"` or `"prod"` for target-driven macro logic to work.

## Profiles Architecture

Two `profiles.yml` files per school/network project:

- **`.dbt/profiles.yml`** — local dev + dbt Cloud, multiple targets
  (`dev`/`staging`/`prod`)
- **`src/dbt/<project>/profiles.yml`** — shipped with code, used by Dagster

Source-system projects only appear in `.dbt/profiles.yml` (not shipped to
Dagster — they run as packages inside school projects).
