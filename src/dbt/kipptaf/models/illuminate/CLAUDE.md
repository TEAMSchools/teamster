# CLAUDE.md — `models/illuminate/`

Illuminate DnA (assessments) and Repositories (custom student data tables). The
largest model directory in the repo at ~537 `.sql` files — **but 450 of them are
disabled.** Read the next section before grepping or building here.

## `fivetran/` is dead — only `dlt/` is live

`illuminate.fivetran` is `+enabled: false` at the project level
(`dbt_project.yml`). It holds the pre-dlt Fivetran ingestion, including
`fivetran/staging/repositories/archive/` (383 models) kept for historical
reference.

| Subtree     | `.sql` files | Enabled |
| ----------- | ------------ | ------- |
| `dlt/`      | 87           | yes     |
| `fivetran/` | 450          | **no**  |

A bare `grep -r` in this directory returns mostly `fivetran/` hits. Scope
searches to `dlt/`, or you will read and "fix" dead code. Same trap when
`grep`-ing for a column name across `src/dbt/` — the archive dominates the
results.

## `dlt/` layout

```text
dlt/
  sources-illuminate.yml               # DnA + public + standards + codes sources
  sources-illuminate-repositories.yml  # 359 repository_* source tables
  staging/            27 models  — one per DnA/public/standards/codes table
  staging/repositories/  49 models — one per staged repository
  intermediate/       11 models
```

Source prefixes in `staging/`: `codes__`, `dna_assessments__`,
`dna_repositories__`, `national_assessments__` (PSAT), `public__`,
`standards__`.

**359 repository source tables are ingested, 49 are staged.** dlt lands every
repository it finds; staging is deliberately selective. A repository existing in
BigQuery does not mean a model exists for it.

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

## Adding a repository is a 3-file change

1. `dlt/staging/repositories/stg_illuminate__dna_repositories__repository_<id>.sql`
   containing only the macro call.
1. An entry in `dlt/staging/repositories/properties.yml`.
1. A `ref()` in the hand-maintained `union_relations` list in
   `dlt/intermediate/int_illuminate__repository_data.sql`.

Miss step 3 and the model builds clean while its data never reaches anything
downstream — no test fails, no error appears.

**Disabled repositories: 365, 413, 428** (`config: enabled: false` in
`properties.yml`). They are correspondingly absent from the union, so the counts
reconcile as 49 files − 3 disabled = 46 refs. Check this list before adding a
`ref()` to `int_illuminate__repository_data`.
