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
  (redirects to `gs://teamster-test/dagster/<project>` when
  `DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT=1`, via inline conditional in each
  `external.location` template)

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

When a PR adds or modifies an external source, flag that the developer must
stage it with `--target staging` before the dbt Cloud CI job will pass.

`stage_external_sources --args "select: ..."` takes a
`<source_name>.<table_name>` selector — not project-qualified. The
project-prefix form (e.g. `kipptaf.google_sheets.<table>`) silently matches zero
sources.

`stage_external_sources` is a `dbt run-operation` — `--threads` doesn't apply.
Running it in parallel across all 5 district projects exhausts BigQuery's
`INFORMATION_SCHEMA.simple_rate.user` quota (429). Serialize across projects, or
run only the project you need.

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

## kipptaf source consumers of district columns

When adding a column or changing values (hash recomposition, restructure) in a
district intermediate consumed by kipptaf via `source()`, ship in two PRs:
district first, wait for Dagster to materialize prod, then kipptaf. The kipptaf
source resolves to prod for `target=staging` (dbt Cloud CI), so coupling fails
CI deterministically. Kipptaf-level test tightenings (e.g. restoring
`severity: error` on a mart PK that depended on the upstream value change)
belong in the follow-up PR.

## dbt logs persist locally

Every `dbt` invocation appends to `<project>/logs/dbt.log` (full output, not
truncated). When a background build's captured output is incomplete, read that
file before re-running the build.

## `dbt ls --output json` stdout is mixed

Stdout interleaves dbt log lines with JSON records. Pipe through `grep '^{'`
before parsing.

## Materialization overrides go in properties yml

Use `config: materialized: <kind>` in `properties/<model>.yml`, not inline
`{{ config(...) }}` in SQL. Create the yml if absent.

## Table→view materialization conversion needs a drop

`create or replace view` does not drop a pre-existing table at the same path —
the conversion silently keeps serving the stale table. Ship table→view
conversions with either an explicit
`DROP TABLE IF EXISTS <project>.<dataset>.<model>` at deploy time, or run
`dbt build --select <model> --full-refresh` once after merge.

## dbt Cloud CI state comparison

`state:modified+` hashes every source node through `{{ target.name }}`
rendering. The CI job and the parse job in its `deferring_environment_id` must
share `target_name`, or every source with the target-conditional schema pattern
hash-mismatches and fans out to rebuild the whole graph.

Auto-retried CI runs invoke `dbt retry`, which replays the prior run's compiled
SQL. After fixing external state (defer relations, transient BQ errors), trigger
a fresh `dbt build` — don't rely on the retry.

## Dev `--defer` for unstaged externals

Dev builds depending on GCS externals (`stg_google_sheets__*` etc.) fail with
"table not found" when those externals aren't staged for the current user. Add
`--defer --state=src/dbt/<project>/target/prod/`. **`--state` path is relative
to `--project-dir`** — repo-root form silently fails with "Could not find
manifest". The prod manifest is refreshed by `.git/hooks/post-merge` on every
`git pull`; if stale, regenerate with
`uv run dbt parse --target prod --project-dir <project> --target-path target/prod`.

## `dbt clone` behavior on BigQuery

- Views fall back to running the view materialization (compiles + runs the model
  SQL) — not a clone, and not free.
- Missing prod relations → silent skip with
  `No relation found in state manifest for <unique_id>`. Treat as a diagnostic
  signal, not an error.
- `--state` manifest must be parsed with `target=prod` so model schemas resolve
  to prod warehouse relations. A staging-target manifest causes every model to
  fall through to view materialization, eventually hitting BigQuery's 16-level
  nested-view limit.
- Pre-existing target relations are skipped unless `--full-refresh` is passed
  ([docs](https://docs.getdbt.com/reference/commands/clone)). Use the flag to
  recreate drifted defer copies.
- From a worktree, pass `--profiles-dir src/dbt/<project>` (Dagster-shipped
  profile, not `~/.dbt/profiles.yml`) and
  `--state /workspaces/teamster/src/dbt/<project>/target/prod` (main repo's
  manifest — skips a worktree-local parse).
- `dbt clone --select 'package:<name>'` matches only source-system package
  models, not district-level overrides with the same name. For cross-project
  staging seeding, omit `--select`.

## Stale dev tables shadow `--defer`

`--defer` uses any existing dev table before falling through to prod, so a stale
dev parent dim produces false-positive `relationships` orphans. Before trusting
a dev relationships warning on a FK, include the parent in `--select` or
`dbt clone --select <parent_dim>` from prod.

Same trap applies to mart PK `unique` tests — a stale dev parent fans out a
date-range join. Query prod before filing upstream bugs or adding defensive
dedupe from a dev mart-test failure.

## Column-rename refactors strand dependent prod views

When a staging column is dropped or renamed and a downstream view's SQL is
updated in the same commit, Dagster's auto-materialize may select only the
staging asset for the deploy run, leaving dependent prod views with their old
stored definition. BigQuery validates view SQL at read time, so every
`relationships` / `unique` test on the staging model fails with
`Name <col> not found inside <alias>; failed to parse view ...`. Confirm the
stored SQL is stale via `INFORMATION_SCHEMA.VIEWS.view_definition`, then
rematerialize each dependent view through Dagster `launch_run` — not a code
change.

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
`sources-bigquery.yml` may omit `schema:` ONLY for tables also declared in
`sources-external.yml`. Tables declared only in the BQ file do NOT inherit and
resolve to bare `<source_name>` (likely a non-existent dataset). However, in
**source-system packages** consumed by district projects, the cross-file schema
merge does not bridge the package/consumer boundary — the consuming project's
schema override won't reach the package-level BQ file. In that case,
`sources-bigquery.yml` must include its own `schema:` (plain `var()` without
target-conditional prefixes, since BQ-native tables are static production data).
Never mix `external:` and non-external active tables in one file. Source-system
projects place source files alongside or inside their model subdirectories, not
at the top-level `models/` directory.

### `{{ project_name }}` in source schemas

- **Source-system projects** (amplify, deanslist, edplan, etc.): use
  `{{ project_name }}`.
- **kipp\* projects** (kipptaf, kippnewark, etc.): hardcode the project name.

### Google Sheets external sources

Declare `columns:` at the source level (parallel to `external:`, not nested
inside it — nested `columns:` silently no-ops back to autodetect). Autodetect
drops columns where every row is NULL and type-infers from data values, so
text-formatted `00000` in Sheets becomes INT64.

```yaml
- name: src_<...>
  external:
    options: { ... }
  columns:
    - name: <Header_Name>
      data_type: STRING
```

### Rebuild staging after sheet edits before testing

After Ops edits a Google Sheet source or after running
`stage_external_sources --target staging`, rebuild downstream `stg_*` tables
(default materialization is `table`) before trusting test results:
`dbt build --select <staging_model>+1 --exclude resource_type:test`. A "drift"
against stale staging is a false positive.

## Shipped Profiles (`src/dbt/*/profiles.yml`)

Dagster-only: default target `prod` + `defer` output. Branch deployments
explicitly pass `target="defer"` via `DbtCliResource`; prod uses the profile
default (no Python override needed). No `GITHUB_USER` — not available in Dagster
deployments. Developers use `<repo-root>/.dbt/profiles.yml` (not
`~/.dbt/profiles.yml`) for full target support.

- **`job_retries`**: dbt-bigquery defaults to `1`, which doesn't absorb
  sustained transient 503s on `client.list_datasets()` at adapter init. Set
  `job_retries: 3` on the `prod` output. Set on all district profiles and
  kipptaf.

## Model Conventions

These conventions apply to **every** dbt project in this directory. Per-project
CLAUDE.md files reference this section rather than repeating it.

### BigQuery type synonyms in contracts

`numeric` and `float64` are NOT synonyms — they're distinct BigQuery types.
Casting to one while declaring the other in YAML passes parse but fails contract
enforcement at build time.

BQ accepts legacy spellings as synonyms: `boolean`/`bool`, `integer`/`int64`,
`float`/`float64`, `decimal`/`numeric`, `bigdecimal`/`bignumeric`. YAML
`data_type` and `INFORMATION_SCHEMA.COLUMNS.data_type` may disagree on spelling
without it being real drift — normalize before comparing.

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

- Project-level `data_tests:` defaults flow through to singular tests too. Drop
  redundant `severity` / `store_failures` / `store_failures_as` from
  singular-test `config()`; keep only per-test fields (`meta.dagster.ref`).
- Staging-layer tests MUST set `config: severity: error` on every test. The
  project default is `warn`, so staging tests without explicit `severity: error`
  silently degrade to warnings and won't fail CI. Intermediate/mart/`rpt_` tests
  may omit the override where a warning is acceptable.
- Removing a `severity: warn` override reverts to project default (`warn`), not
  `error`. To restore `error`, set `config: severity: error` explicitly.
- Unscoped `+config` applies to tests from all installed packages, not just the
  current project

### `dbt_utils.expression_is_true` window-function limit

Compiles to `where not (<expression>)`. BigQuery rejects window functions in
`WHERE`, so the macro can't use `lag()` / `row_number()` / etc. Use a singular
test (`tests/test_*.sql`) for window-based predicates.

### `dbt_utils.expression_is_true` column-level prepends the column

Compiles to `where not (<column> <expression>)` — a column-referencing predicate
like `array_length(role_ids) >= 1` produces
`where not (role_ids array_length(role_ids) >= 1)`. Put predicates that already
name the column at model level, not on the column.

### Singular-test description placement

Top-level `description` on a singular test must go in a properties yml under
`data_tests:` — `config(description="...")` in the SQL lands at
`config.description`, which dbt docs doesn't read. After adding/editing the yml,
run `dbt parse --no-partial-parse`; partial parse caches the unbound state.

### Generic test syntax (dbt 1.11+)

All generic tests (`relationships`, `accepted_values`,
`dbt_utils.unique_combination_of_columns`, etc.) require `arguments:` nesting.
The flat form (without `arguments:`) triggers a deprecation warning:

```yaml
# wrong — flat
- accepted_values:
    values: [a, b]

# right — nested under arguments
- accepted_values:
    arguments:
      values: [a, b]
```

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

Corollary: never add `not_null` tests on `generate_surrogate_key` output — it
never returns NULL.

### Nullable PK inputs need a fallback, not a null-wrap

For a primary key (not an FK), wrapping `generate_surrogate_key` in
`if(col is not null, ..., cast(null as string))` makes the PK nullable and fails
`not_null`. Use a fallback discriminator inside the hash inputs:
`coalesce(cast(primary_id as string), secondary_id)`. The secondary id must be
unique-per-row within the rows the primary would have disambiguated — otherwise
rows with NULL primary collide on the placeholder hash and fail `unique`.

### dbt_utils.deduplicate `order_by` on BigQuery

The macro compiles to `array_agg(original order by <expr> limit 1)`. BigQuery
rejects `asc nulls last` and `desc nulls first` inside aggregate `array_agg`.
Use `desc` (default NULLS LAST) or `(col is null) asc` instead of explicit
`nulls last` with ascending sort.

**`partition_by` must match the downstream join key**, not the source PK.
Partitioning by the source's natural key leaves multiple rows that share the
intended join column, which then fan out at the join site. Use
`(col = 'sentinel') asc` in `order_by` to demote a specific value when rows tie
on the chosen partition key.

### sqlfluff ST03 on dbt_utils.deduplicate input CTEs

A CTE referenced only via `dbt_utils.deduplicate(relation="<cte>")` fails
sqlfluff ST03. Add
`# trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below`
above the CTE.

### Don't inline CASE expressions in generate_surrogate_key

`dbt_utils.generate_surrogate_key(["case <col> when ... end"])` compiles via
Jinja's implicit-string-concat across adjacent list elements — unreviewable, and
a comma inserted between fragments silently changes the SQL. Derive the computed
value as a named column in an upstream CTE, then hash that column.

### Namespace UNION-ed `generate_surrogate_key` branches

When two `generate_surrogate_key()` calls feed `UNION ALL` into one key column,
prepend a branch-discriminator literal (`"'left'"` / `"'right'"`) as the first
input. `generate_surrogate_key` stringifies inputs, so `'1'` (string) and `1`
(int) collide when remaining inputs align.

### Canonical attributes from a partition

Use `first_value(... order by <pk>)` for every attribute, not separate `min()`
calls — independent mins on different columns can pick from different rows in
the same partition.

### SQL conventions

- **Soft-delete filters**: Apply in the **staging model**, not in downstream
  `ON` clauses. Deleted rows should never reach intermediate or mart models.
  Omit columns whose value is predetermined by the WHERE filter (e.g.,
  `deleted_at` after `WHERE deleted_at IS NULL`) — they add no signal.
- **Google Sheets external-table case**: `select *,` in a staging model inherits
  the sheet header case (often PascalCase). Contract-enforced YAML column names
  must match that case, or use explicit `<raw> as <renamed>` aliasing in the
  staging SQL. Don't rename columns in `sources-external.yml` just to normalize
  case — that rebuilds the external table and forces sheet-header coordination.
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
- **DATE literal across UNION ALL branches needs explicit cast**: BQ coerces
  `'9999-12-31'` to DATE inside `coalesce(date_col, ...)` but NOT across UNION
  ALL branches when one side is CTE-typed STRING. Use
  `cast('9999-12-31' as date)`. Avoid the `date '9999-12-31'` typed-literal
  form.
- **Pre-compute `lag()` / `format()` inputs in the source CTE** so the
  comparison CTE compares plain columns. Avoids duplicating the expression
  inside `lag(expr)` and the bare-column reference.
- **Timezone-aware today**:

  ```sql
  current_date('{{ var("local_timezone") }}')
  ```

- **sqlfluff ST09 (join order)**: ON-clause predicates list the
  earlier-referenced table on the left, including predicates inside a current
  join that reference a prior-joined table. After
  `from A ... join B ... join C on X`, predicates referencing both `B` and `C`
  write `B.x = C.y`, not `C.y = B.x`.
- **BigQuery-reserved CTE names**: `groups` is reserved (window-frame syntax
  `OVER (... GROUPS BETWEEN ...)`). A CTE named `groups` fails parsing with
  "Expected keyword SELECT but got keyword GROUPS". Use `reporting_groups` or
  similar.
- **`select *` inside UNION ALL CTEs trips CV03**: sqlfluff requires a trailing
  comma after the last column, but `select *` has nothing to trail. Enumerate
  columns explicitly in each UNION branch.

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

- **Read `properties.yml` before modifying a model.** It carries the
  authoritative `description:`, `data_tests:`, contract column types, and
  `config.meta.source_column` pointers. Copy-pasted column blocks rot here first
  — verify every paste against the current source.
- All new or modified models require `description:` on the model and every
  column. Profile staging data via BigQuery MCP; infer downstream from parents.
  Describe calculated fields by logic. Use qualitative language — no stats.
- Columns with **per-column** `data_tests:` should be sorted to the top of the
  `columns:` list for visibility. Model-level composite tests
  (`dbt_utils.unique_combination_of_columns`, etc.) do not trigger this rule —
  they go in the model-level `data_tests:` block ABOVE `columns:`, and their
  referenced columns can stay in their natural / contract order.
- Test placement by arity: single-column tests (`unique`, `not_null`, etc.) go
  on the column itself. Multi-column tests
  (`dbt_utils.unique_combination_of_columns`, etc.) go at model level in a
  `data_tests:` block placed ABOVE the `columns:` block.
- Column renames for semantic clarity (e.g., boolean prefixing with `is_`,
  reserved word aliases) belong in the staging model, not downstream.
- Data and column semantics — code values, identifier formats, join keys, grain
  notes — belong in the model's `description:` (or `config.meta`), not
  CLAUDE.md. CLAUDE.md is for workflow conventions and tooling guidance only.
- YAML `description:` is for what/why a column or model computes. Don't put
  TODOs, history, migration plumbing, or tracking-issue refs (`#3142`, etc.) in
  descriptions — those go in inline SQL comments at the derivation site.

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
- **No self-aliases** (sqlfluff AL09): drop `as <name>` when the output name
  equals the source column, including backticked reserved words
- **String literals**: single quotes only (no double quotes)
- **Line length**: 88 characters max

Do not flag code that follows these rules.
