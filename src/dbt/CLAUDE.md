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

## District Variable Defaults

All district projects share these variables (override via `dbt_project.yml`):

- `current_academic_year`, `current_fiscal_year` — updated each July; get
  current values from any district's `dbt_project.yml`
- `local_timezone` — `America/New_York`
- `cloud_storage_uri_base` — `gs://teamster-<project>/dagster/<project>`
- `powerschool_external_location_root` —
  `gs://teamster-<project>/dagster/<project>/powerschool` (ODBC districts only)

Exceptions: `kippnewark` adds `iready_schema: kippnj_iready` and
`renlearn_schema: kippnj_renlearn`. `kipptaf` has
`bigquery_external_connection_name` — see its CLAUDE.md.

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

When a PR adds or modifies an external source, flag that the developer must
stage it with `--target staging` before the dbt Cloud CI job will pass.

## Source Schema Resolution

dbt source YAML `schema:` fields render with `SchemaYamlContext`, which only
provides `env_var()`, `var()`, `target`, and `project_name` — **not custom
project macros** (dbt-labs/dbt-core#6056). Use standardized inline Jinja with
`target.name` checks, not macro calls. Use single-line quoted strings — YAML
multiline scalars (`|`, `>`) cause whitespace issues with `{%- -%}` tags.

Two inline patterns (see spec for details):

- **Source schema** (all sources except kipptaf cross-regional): prefixes for
  `defer` and `dev` targets
- **Region source schema** (kipptaf `sources-kipp*` files only): prefixes for
  `dev` only (`defer` resolves to production)

## Source File Conventions

- **`sources-bigquery.yml`** — BQ-native sources (Airbyte, Fivetran, frozen
  archives, AppSheet sync, etc.). Plain schema, no target-conditional prefix.
  Tables may be active or `enabled: false`.
- **`sources-external.yml`** — GCS/Google Sheets external sources. Use the
  target-conditional inline Jinja prefix pattern.
- **`sources-<project>.yml`** — kipptaf regional sources pointing to district
  project datasets. Use the region schema pattern (dev-only prefix).

A single integration may have both files under the same source `name:` — dbt
merges at parse time. When both exist **in the same project**,
`sources-bigquery.yml` may omit `schema:` (inherits from the external file).
However, in **source-system packages** consumed by district projects, the
cross-file schema merge does not bridge the package/consumer boundary — the
consuming project's schema override won't reach the package-level BQ file. In
that case, `sources-bigquery.yml` must include its own `schema:` (plain `var()`
without target-conditional prefixes, since BQ-native tables are static
production data). Never mix `external:` and non-external active tables in one
file. Source-system projects place source files alongside or inside their model
subdirectories, not at the top-level `models/` directory.

### `{{ project_name }}` in source schemas

- **Source-system projects** (amplify, deanslist, edplan, etc.): use
  `{{ project_name }}`.
- **kipp\* projects** (kipptaf, kippnewark, etc.): hardcode the project name.

## Shipped Profiles (`src/dbt/*/profiles.yml`)

Dagster-only: default target `prod` + `defer` output. Branch deployments
explicitly pass `target="defer"` via `DbtCliResource`; prod uses the profile
default (no Python override needed). No `GITHUB_USER` — not available in Dagster
deployments. Developers use `.dbt/profiles.yml` for full target support.

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

- Do not add `store_failures: true` to individual tests — the project default
  handles it
- Tests that must error (not warn) need explicit `config: severity: error`
- Unscoped `+config` applies to tests from all installed packages, not just the
  current project

### dbt_utils test syntax (dbt 1.11+)

`dbt_utils.unique_combination_of_columns` and `relationships` tests require
`arguments:` nesting. The flat form (without `arguments:`) triggers a
deprecation warning.

### Date-range joins

Use half-open intervals for enrollment date-range joins — `BETWEEN` causes
fan-out when consecutive enrollments share a boundary date:

```sql
-- wrong: matches both enrollments on the shared boundary
and cc.dateenrolled between enr.entrydate and enr.exitdate

-- right: half-open interval
and enr.entrydate <= cc.dateenrolled
and enr.exitdate > cc.dateenrolled
```

### Enrollment join fan-out (known upstream issue)

`base_powerschool__student_enrollments` and
`base_powerschool__course_enrollments` have genuinely overlapping date ranges
for some students at the same school/section (not just boundary overlaps).
Half-open interval joins reduce but don't eliminate fan-out. When a date-range
enrollment/CC join still produces duplicates, add a `qualify` tiebreaker picking
the latest `entrydate` / `cc_dateenrolled`, with a `-- TODO: #3633` comment.

### Nullable surrogate keys

`dbt_utils.generate_surrogate_key()` hashes NULL inputs into a deterministic
placeholder string — it never returns NULL. When a surrogate key column can be
null (e.g., from a LEFT JOIN), wrap the call:

```sql
if(
    source_column is not null,
    {{ dbt_utils.generate_surrogate_key(["source_column"]) }},
    cast(null as string)
) as fk_column,
```

Without this, relationship tests check the placeholder hash against the parent
dimension and fail.

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
