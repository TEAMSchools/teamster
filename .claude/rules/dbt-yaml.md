---
paths:
  - "**/src/dbt/**/*.yml"
---

# dbt YAML conventions

Loads on the first read of a `.yml` file under `src/dbt/`: properties, sources,
tests, and unit-test fixtures. Applies to every dbt project in the repo.
Project-level and cross-cutting rules: `src/dbt/CLAUDE.md` and
`.claude/rules/dbt-models.md`.

## External Table Pattern

When a PR adds or modifies an external source, flag that the developer must
stage it with `--target staging` before the dbt Cloud CI job will pass.

**A brand-new external source cannot be staged until its asset has materialized
once** — Avro autodetect needs >=1 file. Pre-merge, open the PR non-draft so the
branch deployment builds, materialize the asset there, then stage with the
`gs://teamster-test/...` `--vars` override below. Post-merge, launch that asset
in prod IMMEDIATELY: external sources are excluded from the deps gate
(`any_deps_missing().ignore(_EXTERNAL_SOURCE_SELECTION)` in
`core/automation_conditions.py`), so the first post-deploy tick requests the new
staging model and its `stage_external_sources` fails on the still-empty prod
prefix.

**Sheets externals need no manual post-merge prod re-stage.** The
`build_dbt_assets` stage→refresh→build flow re-stages the prod external and
rebuilds the `stg_` table on the next tick. The "launch that asset in prod
IMMEDIATELY" rule above is for NEW Avro/GCS sources only. Verify with
`INFORMATION_SCHEMA.COLUMNS` on the prod external before filing a manual
re-stage as outstanding work.

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
Running it in parallel across all five `kipp*` projects exhausts BigQuery's
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

### Materialization overrides go in properties yml

Use `config: materialized: <kind>` in `properties/<model>.yml`, not inline
`{{ config(...) }}` in SQL. Create the yml if absent.

### Multi-line SQL in YAML `data_tests:` expressions

Use literal block (`|`), not folded (`>-`). trunk-fmt reflows past 80 chars and
the folded scalar collapses the inserted newline INSIDE a quoted SQL string
literal, producing `Unclosed string literal` at test runtime. Literal block
preserves newlines as newlines; multi-line SQL is fine.

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

- **Header autodetect needs type variation.** BigQuery only treats row 1 as a
  header when it differs in type from the data below. An all-STRING range (e.g.
  a narrowed name-only crosswalk) autodetects as `string_field_0`,
  `string_field_1` — which fails a contracted `select *`. Declare `columns:`
  explicitly for any all-string range; `skip_leading_rows: 1` still drops the
  header.
- **To narrow a Sheets source, add a new named range and move `sheet_range`**
  (`src_x` → `src_x_v2`), don't delete sheet columns — AppSheet and other
  non-dbt consumers read the same tab. Version only the range; keep the source
  `name:` and Dagster asset key. Precedent:
  `src_google_sheets__people__locations_v3`.
- **Phantom empty rows**: a Sheet's full grid (often ~1000 rows) lands as
  null-key rows in the external table → staging `not_null`/`unique` key tests
  fail with ~N results. Filter them in the staging model:
  `where <key> is not null` (e.g.
  `stg_google_sheets__finance__enrollment_targets`).
- **New sheet column vs `select *` contract**: a contract-enforced `select *`
  Sheets staging model breaks the instant Ops adds a column — declare the new
  column in the staging `properties.yml` (and `columns:` in the source) in the
  same change, or CI fails on the undeclared column.

### Rebuild staging after sheet edits before testing

After Ops edits a Google Sheet source or after running
`stage_external_sources --target staging`, rebuild downstream `stg_*` tables
(default materialization is `table`) before trusting test results:
`dbt build --select <staging_model>+1 --exclude resource_type:test`. A "drift"
against stale staging is a false positive.

Google Sheets externals read the sheet **live**, so a _value_ edit (not a new
column) is picked up by rebuilding the `stg_` model into your dev schema
(`dbt build --select <model> --target dev --defer --state <abs prod manifest>`)
— no `stage_external_sources` needed (it's classifier-blocked anyway). Use this
to verify an Ops sheet fix, then query the rebuilt `zz_<user>_*` table.

Never judge CURRENT sheet content from the prod `stg_*` table — it is a table
frozen at the last prod build, not a live read, so it reports pre-edit values
indefinitely. Rebuild into dev (or query the external directly) first.

### BigQuery type synonyms in contracts

`numeric` and `float64` are NOT synonyms — they're distinct BigQuery types.
Casting to one while declaring the other in YAML passes parse but fails contract
enforcement at build time.

BQ accepts legacy spellings as synonyms: `boolean`/`bool`, `integer`/`int64`,
`float`/`float64`, `decimal`/`numeric`, `bigdecimal`/`bignumeric`. YAML
`data_type` and `INFORMATION_SCHEMA.COLUMNS.data_type` may disagree on spelling
without it being real drift — normalize before comparing.

### Uniqueness tests

**History-carrying staging (active-flag + superseded rows)**: scope the key
`unique` test `where: <active_flag>` — a plain `unique` false-fails on
legitimately-superseded inactive rows that repeat the key.

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
- **`accepted_values` passes NULLs** — it compiles to
  `where value not in (...)`, which NULL never satisfies. Every enum column that
  must be non-null carries `not_null` too, including one a `coalesce` makes
  non-null by construction. **Never delete a `not_null` from a column that
  carries `accepted_values`.** It is not vacuous, whatever the SQL looks like —
  the pairing is the only thing making the enum test reject NULL.
- **Never add `not_null` to a column that cannot be NULL by construction.** It
  can never fail, and it still costs a full BigQuery scan per CI run — on a view
  mart that scan re-expands the entire upstream chain. Non-nullable by
  construction means every definition site is one of: an unwrapped
  `generate_surrogate_key`, a `coalesce` / `ifnull` with a non-null default, a
  literal in every UNION branch, or `count(...)`. The `accepted_values` pairing
  above overrides this rule; nothing else does.
- **Disabling a model does NOT disable its tests.** `config: enabled: false` in
  properties yml moves the model to `disabled` but leaves every test in `nodes`
  (verified with `--no-partial-parse`), still scanning the stale prod relation.
  Add `config: enabled: false` to each test as well.

### An FK check belongs on the pre-join model, as a column `relationships` test

A `relationships` test on a model built through an INNER JOIN to its parent is
vacuous — the join already dropped every unmatched row. Put it on the staging
model feeding the join, as a column-level generic (precedent:
`stg_collegeboard__ap.yml`), not a bespoke `*_resolves` singular test.

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

Every `expect` row must list the **same columns** — dbt builds them as
`UNION ALL` and does NOT null-fill omitted keys, so uneven rows fail with
`Queries in UNION ALL have mismatched column count`. Put every asserted column
in every row, `null` for empties.

**A column ADD breaks that model's OWN unit test** — an `expect` block
enumerates every output column, so the new column must be added there too. If
the column is a raw passthrough, `expect` carries the UNnormalized value, not
the normalized value its sibling scalar columns assert.

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
- Columns with **per-column** `data_tests:` must be sorted to the top of the
  `columns:` list for visibility — including after a change that strips a
  column's last test. Reorder freely under `contract: enforced`: BigQuery
  matches contract columns by name, not position (`fct_survey_responses` already
  differs from its `select` order and builds clean). Model-level composite tests
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
- The reverse also holds: rationale that needs no code context belongs in
  `description:`, not an inline SQL comment. Keep SQL comments to what a reader
  of that line cannot see — a non-obvious fallback, why a filter exists. The
  repo's existing multi-paragraph SQL comments are not a precedent to extend.
