# CLAUDE.md — `models/illuminate/`

Illuminate DnA (assessments) and Repositories (custom student data tables). The
largest model directory in the repo, **but most of its `.sql` files are
disabled.** Read the next section before grepping or building here.

## `fivetran/` is dead — only `dlt/` is live

`illuminate.fivetran` is `+enabled: false` at the project level
(`dbt_project.yml`). It holds the pre-dlt Fivetran ingestion, including
`fivetran/staging/repositories/archive/`, kept for historical reference, and
most of this directory's `.sql` files.

A bare `grep -r` in this directory returns mostly `fivetran/` hits. Scope
searches to `dlt/`, or you will read and "fix" dead code. Same trap when
`grep`-ing for a column name across `src/dbt/` — the archive dominates the
results.

## `dlt/` layout

```text
dlt/
  sources-illuminate.yml               # DnA + public + standards + codes sources
  sources-illuminate-repositories.yml  # one source table per loaded repository
  staging/            27 models  — one per DnA/public/standards/codes table
  staging/repositories/  one model per staged repository
  intermediate/       11 models
```

Source prefixes in `staging/`: `codes__`, `dna_assessments__`,
`dna_repositories__`, `national_assessments__` (PSAT), `public__`,
`standards__`.

**dlt loads only the repositories its config lists.** Each `repository_<id>`
table is named in
`src/teamster/code_locations/kipptaf/dlt/illuminate/config/illuminate.yaml`, so
a repository created in Illuminate after the last edit never reaches BigQuery.
Its metadata still does: `repositories`, `fields`, and `repository_grade_levels`
load for every repository. A model that lists repositories from
`int_illuminate__repositories` therefore shows the new one with no data, and
nothing fails. Staging is selective too: a repository table in BigQuery does not
mean a model exists for it.

## Repository models: the filename is the config

Every file in `dlt/staging/repositories/` is a one-liner:

```sql
{{ illuminate_repository_unpivot(model.name) }}
```

`illuminate_repository_unpivot` (in `kipptaf/macros/illuminate.sql`) derives the
repository id by string-replacing the prefix out of the **model name**, then
resolves `source("illuminate_dna_repositories", "repository_<id>")`. Renaming
the file silently repoints it at a different source table. There is no id
argument to check against.

The macro calls `adapter.get_columns_in_relation` at parse time and unpivots
whatever columns exist; an empty or missing relation compiles to a null-typed
stub instead of failing. Columns are therefore data-driven and unknowable at
parse — which is why `contract: enforced` is **`false`** for
`dlt/staging/repositories/` alone, overriding the project-wide `true` for
staging. Do not "fix" that override.

## Adding a repository: 6 places in 2 projects

The first 2 are Dagster files under
`src/teamster/code_locations/kipptaf/dlt/illuminate/`; the rest are relative to
this directory.

1. `config/illuminate.yaml`: `- table_name: repository_<id>` at the top of the
   second `dna_repositories` block.
1. `schedules.py`: the asset key in the daily schedule's `target`. Without it
   the table loads once and never refreshes.
1. `dlt/sources-illuminate-repositories.yml`: a source entry with the Dagster
   `asset_key` meta, copied from the one before it.
1. `dlt/staging/repositories/stg_illuminate__dna_repositories__repository_<id>.sql`
   containing only the macro call.
1. An entry in `dlt/staging/repositories/properties.yml`.
1. A `ref()` in the hand-maintained `union_relations` list in
   `dlt/intermediate/int_illuminate__repository_data.sql`.

Miss any step and the data never reaches anything downstream, with no error.
Only a Sight Words Quiz is caught, by the warn test
`stg_illuminate__dna_repositories__repositories__sight_words_have_scores`, a
week after its date administered. After the deploy, launch the new dlt asset in
Dagster to get the data before the next daily tick.

Disabled repositories: 365, 413, 428 (`config: enabled: false` in
`properties.yml`). They are absent from the union. Check this list before adding
a `ref()` to `int_illuminate__repository_data`.
