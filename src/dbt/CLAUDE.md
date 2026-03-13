# CLAUDE.md — `src/dbt/`

This file provides guidance to Claude Code (claude.ai/code) when working with
dbt projects in this directory.

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

- **`GROUP BY ALL`**: Always list grouping columns explicitly.
- **`SELECT *` in the final SELECT of `rpt_` or mart models**: Always list
  columns explicitly. Pass-through CTEs (`select * from ref(...)`) are fine.
- **Filter conditions in `ON` vs `WHERE`**: Row-filter conditions on the
  preserved table belong in `WHERE`, not `ON` (except `FULL JOIN`).

### Documentation

Column-level documentation belongs in the model's properties YAML as a
`description:` field, not as inline SQL comments.

### Legacy `base_` prefix

Existing `base_` models are being renamed to `int_`
([#2541](https://github.com/TEAMSchools/teamster/issues/2541)). Do not create
new `base_` models.
