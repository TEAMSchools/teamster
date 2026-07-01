# CLAUDE.md — `src/dbt/`

## Overview

Sixteen dbt projects organized into three tiers:

| Tier                  | Projects                                                                                                                    | Purpose                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Source-system**     | `amplify`, `deanslist`, `edplan`, `finalsite`, `focus`, `iready`, `overgrad`, `pearson`, `powerschool`, `renlearn`, `titan` | Clean and contract-enforce raw data from one source system    |
| **District-specific** | `kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`                                                                     | Combine source packages for a single district                 |
| **Network analytics** | `kipptaf`                                                                                                                   | Cross-district marts, reporting, and extracts for the network |

## Project Dependency Map

```text
amplify ──────┐
deanslist ────┤
edplan ───────┤
finalsite ────┤
focus ────────┤                ┌─ kippnewark ──┐
iready ───────┼── (packages) ─┼─ kippcamden ───┼── (sources) ── kipptaf
overgrad ─────┤                ├─ kippmiami ───┤
pearson ──────┤                └─ kipppaterson ─┘
powerschool ──┤
renlearn ─────┤
titan ────────┘
```

Not every district uses every source package. See each district project's
CLAUDE.md for its active packages.

Authoritative consumer list for a source-system package:
`grep -l 'local: ../<pkg>' src/dbt/*/packages.yml`. The district "Active Source
Packages" prose drifts; `packages.yml` is ground truth. `kipptaf` consumes most
source data via `source()`, not as a package.

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
`renlearn_schema: kippnj_renlearn`. All five `kipp*` projects (the four
districts plus `kipptaf`) set `bigquery_external_connection_name` to the
`biglake-teamster-gcs` connection; source-system projects default it to `null`.
See `kipptaf`'s CLAUDE.md.

## Variable Override Pattern

Source-system projects declare variables with null/zero defaults
(`bigquery_external_connection_name: null`, `current_academic_year: 0`, etc.).
Consuming district projects override these in their own `dbt_project.yml`.

## External Table Pattern

When a PR adds or modifies an external source, flag that the developer must
stage it with `--target staging` before the dbt Cloud CI job will pass.

**AVRO external tables autodetect schema from the LAST ALPHABETICAL file.** To
evolve an Avro source's schema, the new-schema file must sort last — materialize
the MAX partition (latest hive `_dagster_partition_date=`). Mixed old/new files
otherwise pick up the old (earlier-sorting) schema.

**A metadata-cached Avro external can read a field NULL downstream though the
GCS file is correct — two distinct failure modes, both surfaced by #4151:**

- _Schema heterogeneity (deterministic)._ After a schema add + partial backfill,
  old-schema files (field absent) and new-schema files (field present) coexist.
  A query scanning both resolves one Avro reader schema and drops the new field
  for the WHOLE scan — even the new files that hold it. The field still
  _declares_ fine (autodetect from the last-alphabetical file) so it queries
  without error and null-fills on old-only scans, but a `stg_*` model that scans
  full partition history always includes old files, so the column reads NULL
  everywhere. A cache refresh / rebuild does NOT fix it — only homogenizing the
  files does (`scripts/reencode_avro_partitions.py` re-encodes every partition).
- _Cache staleness (intermittent)._ `build_dbt_assets`
  (stage→refresh→`dbt build`) races BigLake metadata-cache convergence after a
  `create or replace` / overwrite-in-place: the
  `refresh_external_metadata_cache` `CALL` returning DONE does NOT mean
  queryable-fresh (lag seconds→hours, non-monotonic), so a just-materialized
  partition reads NULL downstream.

Verifying: `bq --nouse_cache` exposes the TRUE cached state (the BQ results
cache and the BigQuery MCP otherwise return stale-but-fresh-looking counts).
Selecting `_FILE_NAME` forces a live read that BYPASSES the metadata cache
(ground truth vs. staleness) but does NOT bypass schema heterogeneity (a
mixed-schema scan still drops the field), and it contaminates the whole query to
a live read. So `_FILE_NAME` is ground truth only within a single-schema scan
(one partition); never mix it into a cached-path check.

dbt Cloud CI runs `dbt build` only (never `stage_external_sources`) → it reads
the existing `zz_stg` external table as-is. To make CI see a new schema before
prod Avro is updated: materialize the max partition locally (the Avro IO manager
uploads to GCS even with `test=True` →
`gs://teamster-test/dagster/<asset_key>/`), then
`stage_external_sources --target staging --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/<project>, ext_full_refresh: true}'`.
Re-stage to the prod location only post-merge once the prod re-pull lands — a
pre-merge re-stage reverts CI to the old (narrow) schema.
`stage_external_sources` SKIPs an existing table unless
`ext_full_refresh: true`.

Re-pulling a source asset refreshes the **prod** external
(`<district>_<source>.src_*`) but NOT the `zz_stg_*` staging external that
`--target staging` builds and dbt Cloud CI read — those stay frozen until
`stage_external_sources --target staging` re-runs. A BigQuery MCP query against
the prod external passing does NOT mean a staging build / CI will; verify
against `zz_stg_*`.

Contract enforcement matches columns by **name + type, not YAML order** — new
contract columns may be added anywhere in `properties.yml`. Regenerate a large
struct `data_type` by pulling it verbatim from `INFORMATION_SCHEMA.COLUMNS` of
the staged table; don't hand-transcribe.

A multi-type Avro union (e.g. a Pydantic `bool | str | list[str]` field) lands
in a BigQuery external table as a named
`STRUCT<boolean_value, string_value, array_string_value>`, not a scalar — read
the typed subfield (`.string_value` / `.array_string_value` / `.boolean_value`).

dbt CLI runs locally for Claude: `DBT_PROFILES_DIR` (repo `.dbt`) + ADC →
`dbt debug` / `build` / `run-operation --target staging` connect with no
1Password (BigQuery uses ADC, not the 1Password bootstrap). `--target prod` runs
(`dbt build` / `run`) are blocked by the auto-mode classifier as production
deploys even with verbal approval — hand prod runs to the user. `dbt compile` /
`parse --target prod` are NOT blocked (no warehouse write) — use them to
validate model SQL/refs locally. `stage_external_sources --target staging` with
`ext_full_refresh: true` is also classifier-blocked (drops/recreates shared
`zz_stg` tables) — needs direct user authorization in the immediately-preceding
turn, else hand off.

`stage_external_sources --args "select: ..."` takes a
`<source_name>.<table_name>` selector — not project-qualified. The
project-prefix form (e.g. `kipptaf.google_sheets.<table>`) silently matches zero
sources. Multiple space-separated selectors work in one call:
`select: pearson.src_pearson__njsla pearson.src_pearson__njsla_science`.

`stage_external_sources` is a `dbt run-operation` — `--threads` doesn't apply.
Running it in parallel across all 5 district projects exhausts BigQuery's
`INFORMATION_SCHEMA.simple_rate.user` quota (429). Serialize across projects, or
run only the project you need.

## Source-package staging builds in every consuming district

A source-system package's staging models build in **every** district that
imports it, but only carry data where that source's Dagster ingestion is wired
per code location — e.g. `stg_finalsite__contacts` builds in all four districts
(all import the `finalsite` package) but only `kippmiami` materializes the
contacts asset; the other three build it empty. Before promoting a district
model to a shared source package, confirm the source ingestion exists in every
consuming district, or the promoted model builds empty there (or fails on a
missing external).

To gate an _optional_ package layer per region, split the package into
method/source subfolders (`api/`, `sftp/` — the amplify convention) and set
`<package>: <method>: +enabled: false` in the unwired district's
`dbt_project.yml`. Keep network-wide feeds enabled everywhere (e.g. finalsite
SFTP `status_report` is consumed by kipptaf in all regions; only `api` is
Miami-only). Method subfolders don't change asset keys.

**Merging `dbt_project.yml` package configs can silently duplicate a top-level
key.** When two branches each add `models: <package>:` (or `sources:`) at
different positions, git's line-merge keeps BOTH with no conflict marker (later
wins; may be invalid YAML). After merging a `dbt_project.yml`, grep for
duplicate package keys and consolidate.

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
district model consumed by kipptaf via `source()`, ship in two PRs: district
first, wait for Dagster to materialize prod, then kipptaf. kipptaf
`sources-kipp*` resolve to the `zz_stg_*` staging copies for `target=staging`
(dbt Cloud CI), NOT prod — and a district prod merge does NOT refresh those
copies, so kipptaf CI keeps reading the stale `zz_stg_*` table (missing the new
column) and fails deterministically. Refresh it before/with the kipptaf PR:
`dbt clone --select <model> --target staging --state src/dbt/<district>/target/prod --full-refresh --project-dir src/dbt/<district>`
per district (metadata-cheap when the prod relation is a TABLE; needs direct
user authorization — recreates shared `zz_stg_*` tables), then trigger a fresh
CI `dbt build` (not `dbt retry`, which replays stale compiled SQL).
Kipptaf-level test tightenings (e.g. restoring `severity: error` on a mart PK
that depended on the upstream value change) belong in the follow-up PR.

Alternative single-PR pattern (CI schema branching + cross-project clone): see
`src/dbt/kipptaf/CLAUDE.md` → "Single-PR cross-project workflow".

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

## Fresh worktree needs `dbt deps`

A newly-created worktree has no `dbt_packages/`. Run
`uv run dbt deps --project-dir <worktree>/src/dbt/<project>` once before any
`dbt build` / `test` / `clone` there — otherwise it errors with "N package(s)
specified in packages.yml, but only 0 package(s) installed".

## Building a source-system package model locally

Source-system package models (`focus`, `amplify`, etc.) have no resolvable vars
standalone — build/test them via a **consuming district** project-dir with that
district's prod manifest for `--defer` (e.g. focus → kippmiami):
`uv run dbt build --select <model> --project-dir src/dbt/kippmiami --defer --state src/dbt/kippmiami/target/prod --target dev`.

## Dev `--defer` for unstaged externals

Dev builds depending on GCS externals (`stg_google_sheets__*` etc.) fail with
"table not found" when those externals aren't staged for the current user. Add
`--defer --state=src/dbt/<project>/target/prod/`. **`--state` path is relative
to `--project-dir`** — repo-root form silently fails with "Could not find
manifest". The prod manifest is refreshed by `.git/hooks/post-merge` on every
`git pull`; if stale, regenerate with
`uv run dbt parse --target prod --project-dir <project> --target-path target/prod`.

**From a worktree**, `--state` must be absolute
(`/workspaces/teamster/src/dbt/<project>/target/prod`). The relative form
resolves under the worktree, which has no `target/prod/` — only the main repo's
manifest is refreshed by `post-merge`.

## Multi-line SQL in YAML `data_tests:` expressions

Use literal block (`|`), not folded (`>-`). trunk-fmt reflows past 80 chars and
the folded scalar collapses the inserted newline INSIDE a quoted SQL string
literal, producing `Unclosed string literal` at test runtime. Literal block
preserves newlines as newlines; multi-line SQL is fine.

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

## `dbt_utils.union_relations` is compile-time

Compiles to the column intersection from source-table
`INFORMATION_SCHEMA.COLUMNS`. New columns added at package-level staging don't
surface at kipptaf-level consumers until district projects rebuild prod. For
single-PR refactors, add transformations at the kipptaf-level wrapper, not at
package level.

**Value-only vs column change**: a value-only edit to a package model needs no
staging — the column set is unchanged, so kipptaf CI compiles and corrected
values land after the next prod rebuild. A column ADD/rename DOES: an unmodified
kipptaf union wrapper is `--defer`'d to the Staging env (not `zz_stg`), so the
new column never appears and downstream models fail `Name <col> not found`. To
land it single-PR, force the wrapper `state:modified` (a doc comment is enough)
AND `dbt build --select <pkg-model> --project-dir <district> --target staging`
into `zz_stg_<district>_<source>` so CI's wrapper rebuild sees the column. The
`state:modified` trigger must be a `.sql` edit (a comment) — a properties.yml
`description` change does NOT mark a model modified. Diagnose which side is
stale from the CI error's `compiled_code` `from` clause: a ref resolving to
`zz_stg_*` was deferred to the stale staging copy; one resolving to
`dbt_cloud_pr_*` was rebuilt on the PR branch.

## Editing a `sources-kipp*.yml` schema fans out `state:modified+`

Changing a source's schema (e.g. adding a `target=staging` branch) marks the
WHOLE source `state:modified` — CI's `state:modified+` builds EVERY kipptaf
model reading it, not just your target. A district model dropped from code but
lingering as a stale prod table is absent from the prod manifest → clone-skipped
→ its kipptaf consumer fails CI `Table not found`. Fix such frozen/retired
tables by declaring them a BQ-native source (`sources-bigquery.yml`, plain
hardcoded schema, no target branch) so kipptaf reads prod regardless of target.

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
merges at parse time.

**When both files exist in the same project:**

- `sources-bigquery.yml` may omit `schema:` ONLY for tables also declared in
  `sources-external.yml`. Tables declared only in the BQ file do NOT inherit and
  resolve to bare `<source_name>` (likely a non-existent dataset).
- Never mix `external:` and non-external active tables in one file.

**In source-system packages consumed by district projects**, the cross-file
schema merge does not bridge the package/consumer boundary — the consuming
project's schema override won't reach the package-level BQ file. In that case,
`sources-bigquery.yml` must include its own `schema:` (plain `var()` without
target-conditional prefixes, since BQ-native tables are static production data).

Source-system projects place source files alongside or inside their model
subdirectories, not at the top-level `models/` directory.

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

- **Phantom empty rows**: a Sheet's full grid (often ~1000 rows) lands as
  null-key rows in the external table → staging `not_null`/`unique` key tests
  fail with ~N results. Filter them in the staging model:
  `where <key> is not null` (e.g.
  `stg_google_sheets__finance__enrollment_targets`).

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
- **`job_execution_timeout_seconds`**: Set to `900` on the `prod` output of all
  five kipp\* profiles. Caps each BigQuery job server-side (`job_timeout_ms`) so
  a runaway single model is cancelled by BigQuery before Dagster's run-level
  `max_runtime` (1800s). Without it, a killed dbt run leaves the in-flight BQ
  job orphaned — dbt does NOT cancel on termination (upstream limitation,
  dbt-core #5275/#9639) — and the zombie `create or replace` can overwrite a
  successful auto-retry's output with staler data. Routine models run <=330s
  network-wide (affected models' p99 <=78s), so 900s won't false-kill legit
  work.
- A dbt **`409 Already Exists: Job <id>`** failure is a `job_retries` collision
  (the original submit succeeded server-side but the response was lost; the
  retry re-sends the same job_id). The job usually **succeeded** — confirm via
  `JOBS_BY_PROJECT` (`state=DONE`, `error_result IS NULL`) before treating it as
  real. The Dagster run-retry absorbs it.

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

- **A test/asset-check re-runs only when its host model materializes, and the
  data-change automation condition re-materializes only TABLE models, not
  views.** To make a check refresh regularly, anchor it to a table-materialized
  model — only `staging/` is table by default; other layers need
  `config: materialized: table` in properties yml (e.g.
  `int_people__staff_roster`). `store_failures_as: table` does NOT affect
  refresh cadence — it only relocates failure rows.
- **Before adding a data-quality test, read the target model's existing
  `data_tests:`.** This repo commonly uses `config.where`-scoped `not_null` /
  `expression_is_true` to flag null-column / drop-from-extract conditions, so
  the coverage you want may already exist and already fire as a warn.
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

### Singular-test `meta.dagster.ref` needs `package:` for cross-package refs

dagster-dbt resolves `meta.dagster.ref` via `(name, package, version)`. Omitting
`package:` defaults to the running project — so a test under
`src/dbt/<source>/tests/` referencing a model in its own package silently misses
the lookup and logs `AssetObservation` across all parents instead of an
`AssetCheckResult` on the intended asset. Always set `package: <source>` for
source-system package tests. Tests in `src/dbt/kipptaf/tests/` don't need it
(refs default to kipptaf).

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

### dbt unit-test fixtures

`given`/`expect` dict scalars must be UNQUOTED — yamllint `quoted-strings` flags
quoted dates/strings as redundant. It fires at pre-push/CI, NOT the pre-commit
fmt hook, so a locally-clean commit fails CI. Unquoted `YYYY-MM-DD` parses
correctly for date columns. Exception: leading-zero strings (`"01"`, `"02"` —
e.g. zero-padded grade codes) must be QUOTED, or yamllint `octal-values` fails
at CI.

Dict-format `given` rows require the mocked ref/source to already exist in the
warehouse (dbt introspects its schema at compile). For array/struct columns
(e.g. `id_attributes`) or a model/source not yet materialized, use input
`format: sql` (inline SELECT) instead — dict format fails introspection. A
column ADDED to an existing upstream in the same PR is also a
fails-introspection case: dbt reads the deferred old-schema relation and rejects
the new column (`Invalid column name '<col>' in unit test fixture`). Building
that upstream into your dev schema first makes the dict fixture pass LOCALLY
while CI still fails — use `format: sql`; don't trust a local unit-test pass for
a same-PR column add.

After a column/contract rename, run the WHOLE directory's unit tests
(`--select "test_type:unit,<fqn.dir>"`, e.g. `test_type:unit,extracts.focus`),
not just the changed model — sibling models mock the same `ref()`/`source()`, so
their `given`/`expect` rows break on the same rename and CI catches what a
single-model run misses.

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

**Picked-row attrs include NULL — don't `coalesce` to a fallback row.** When
`dbt_utils.deduplicate(partition_by=X, order_by=Y)` replicates
`first_value(...) over (partition by X order by Y)` canonical-pick semantics,
the picked row's value is authoritative including NULL.
`coalesce(picked.attr, fallback.attr)` silently substitutes a different row's
value when the canonical pick is NULL — breaks downstream GROUP BY / uniqueness
invariants. Use
`if(<row-belongs-to-picked-partition>, picked.attr, fallback.attr)` to branch on
row-membership, not on value-nullness.

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
- **SFTP `source_file_name`**: drop in the staging model with
  `select * except (source_file_name)` — the SFTP IO adds it to every row
  (`core/utils/functions.py`); a contracted `stg_*` that doesn't except it fails
  the contract on the next re-pull after the ingestion change.
- **Google Sheets external-table case**: `select *,` in a staging model inherits
  the sheet header case (often PascalCase). Contract-enforced YAML column names
  must match that case, or use explicit `<raw> as <renamed>` aliasing in the
  staging SQL. Don't rename columns in `sources-external.yml` just to normalize
  case — that rebuilds the external table and forces sheet-header coordination.
- **No `GROUP BY` without aggregation** — use `DISTINCT` instead (see next rule
  for deduplication constraints).
- **No manual deduplication for dirty data** — do not use `SELECT DISTINCT` or
  `qualify row_number() over (...) = 1` to work around upstream duplicates. Use
  `dbt_utils.deduplicate()` with explicit `partition_by` and `order_by`; add
  `-- TODO:` naming the upstream fix.
- **DISTINCT is allowed for pure grain projection** — every projected column is
  functionally determined by the partition key, so byte-identical tuples
  coalesce. Annotate with a two-line comment:
  `grain projection: every selected column is functionally determined / by the partition key; not a mask for upstream duplicates`.
  If any projected column varies within the partition (`min()`, `first_value()`,
  etc.), use `dbt_utils.deduplicate()` instead.
- **Least/earliest of N nullable columns**:
  `(select min(x) from unnest([c1, c2, ...]) as x)` — aggregate `min` ignores
  NULLs, unlike `least()` (which returns NULL if any arg is NULL). Avoids the
  nested `coalesce(..., sentinel)` + outer-guard pyramid. sqlfluff CV03 wants a
  trailing comma on the inner `select min(x),`; the `unnest([...])` array
  literal must NOT have one (BigQuery rejects a trailing comma in an array).
- **`dbt_utils.generate_surrogate_key` coerces nulls internally** —
  `cast(null as <type>)` and bare `null` hash identically. Don't add the cast.
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
  Exception: `FULL JOIN` conditions referencing one side stay in `ON` — moving
  them to `WHERE` collapses the join to an inner.
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
- **A standalone `select *` takes a trailing comma** (`select *,`) to satisfy
  sqlfluff CV03 (e.g. `stg_overgrad__schools.sql`; a `source` CTE) — distinct
  from the UNION-ALL case above, which must enumerate columns.
- **A projected column whose name equals its source table binds to the whole-row
  STRUCT, not the column**: a bare `address` ref in
  `from {{ source("focus", "address") }}` resolves to the table range variable
  (dbt's component-backtick `` `proj`.`ds`.`address` `` form), so the model
  silently outputs one struct column and the contract fails listing every field
  as `address.<col>`. Read through a `source` CTE
  (`with source as (select *, from {{ source(...) }})`). A single-backtick MCP
  repro `` `proj.ds.table` `` does NOT reproduce it — use component backticks.
- **BigQuery `PIVOT` operator**: pivots ONE value column per aggregate. For a
  mixed-type key-value array, use a multi-aggregate pivot —
  `pivot(max(v_str) as s, max(v_bool) as b, any_value(v_arr) as a for field_name in ('x', ...))`
  — then project the typed column per field (`s_x as x` / `b_x as x`). Output
  columns are `{agg_alias}_{value}`; a SINGLE-aggregate pivot names them by the
  bare value (`'x'` → column `x`). `max()` can't aggregate ARRAY — use
  `any_value()` for array fields.
- **BigQuery `UNPIVOT` excludes null rows** — an entity whose unpivoted columns
  are all null drops out of the result. Harmless for a pure decode companion (a
  left join from staging yields null labels anyway), but when the model also
  LEFT JOINs a separately-computed field (e.g. a `multiple`/array decode), drive
  the final `SELECT` from the full entity list or that field is lost for
  all-null-unpivoted entities.
- **AL09 on struct subfields**: `value.string_value as string_value` trips AL09
  (alias equals the leaf name). Rename to a distinct alias (`as value_string`)
  rather than dropping it when a downstream PIVOT/ref needs the column named.

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

- **Unquoted multi-line `description:` scalars** can't start with a backtick
  (`` `Y` when… ``) or contain `: ` (colon-space, e.g. "types: parent") — both
  fail YAML parsing. Reword (lead with a word; use `—` not `:`).
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
