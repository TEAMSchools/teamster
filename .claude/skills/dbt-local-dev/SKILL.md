---
name: dbt-local-dev
description:
  "Use before any local dbt build, test, clone, compile, or
  stage_external_sources run in this repo, and when a local result disagrees
  with prod or CI: dev schema naming, --defer and --favor-state traps, stale dev
  tables shadowing prod, dbt clone behavior on BigQuery, --empty destroying dev
  relations, building source-system package models through a consuming district,
  and reading dbt logs."
---

# dbt-local-dev

## Local development

### dbt logs persist locally

Every `dbt` invocation appends to `<project>/logs/dbt.log` (full output, not
truncated). When a background build's captured output is incomplete, read that
file before re-running the build.

### Fresh worktree needs `dbt deps`

A newly-created worktree has no `dbt_packages/`. Run
`uv run dbt deps --project-dir <worktree>/src/dbt/<project>` once before any
`dbt build` / `test` / `clone` there — otherwise it errors with "N package(s)
specified in packages.yml, but only 0 package(s) installed".

### Building a source-system package model locally

Source-system package models (`focus`, `amplify`, etc.) have no resolvable vars
standalone — build/test them via a **consuming district** project-dir with that
district's prod manifest for `--defer` (e.g. focus → kippmiami):
`uv run dbt build --select <model> --project-dir src/dbt/kippmiami --defer --state src/dbt/kippmiami/target/prod --target dev`.

**A contract-enforced change needs a real `dbt build` to verify, not a prod
SELECT** — `assert_columns_equivalent` runs only inside `dbt build`/CTAS, so a
SELECT against the prod external validates data/logic but NOT the column set,
and an all-NULL new source column that `select *` passes through slips past
(this shipped a 2nd prod contract failure a build would have caught). For an
Avro/GCS-source model, the dev source copy
`zz_<GITHUB_USER>_<district>_<source>` may be stale/missing the new column —
re-stage YOUR copy first:
`dbt run-operation stage_external_sources --args "select: <source>.<table>" --vars '{ext_full_refresh: true}' --target dev --project-dir src/dbt/<district>`
(personal schema, NOT classifier-blocked, unlike `--target staging`), then
`dbt build --select <model> --target dev`.

**A view build does not evaluate data.** A bad `cast` in a view-materialized
model passes `dbt build` and fails only when a downstream TABLE materializes it.
Never read a green view build as validation of values or types.

**A macro call missing its `{{ }}` fails only at build.** A bare `my_macro()`
instead of `{{ my_macro() }}` is valid SQL — it passes `dbt parse` and sqlfluff,
then fails at BigQuery build with `Function not found`. Build the model to catch
it; parse/lint won't.

**`dbt parse` never resolves macros** — it renders Jinja only far enough to
capture `ref`/`source`/`config`, so a call to a DELETED macro parses clean
whether the caller is enabled or disabled. Parse therefore cannot prove a macro
removal is safe; compilation is the gate, and disabled models are never
compiled. Prove a removal with `grep` for zero enabled call sites plus
`dbt build --empty` over the affected graph.

**`analyses/` are verifiable — compile + BigQuery dry run.** `dbt build` never
runs them, but `dbt compile --select "path:analyses/<f>.sql" --target prod`
followed by `bq query --dry_run` on `target/compiled/.../<f>.sql` resolves every
column against prod schemas — stronger than the `--empty` gate used for models.
Strip leading `--` comment lines first.

### Local dev schema naming

Local dev builds land in `zz_<GITHUB_USER>_<district>[_<source>]` (repo
`.dbt/profiles.yml` dev target, e.g. `zz_cbini_kippnewark_finalsite`) — NOT the
shipped `src/dbt/*/profiles.yml` `zz_dagster_*` schema. Find where a model
actually built with:

```sql
select schema_name
from `teamster-332318`.INFORMATION_SCHEMA.SCHEMATA
where schema_name like '%<frag>%'
```

### Dev `--defer` for unstaged externals

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

Validate a newly-added data test against prod before pushing:
`dbt test --select <model> --target dev --defer --state <prod manifest>` runs
the compiled test SQL against the deferred prod relation — no dev build needed.

A dev `--defer` build of a **table-materialized** mart can fail on a cross-mart
`foreign_key` constraint ("Table X does not have Primary Key constraints") when
the deferred prod parent's DDL lacks the rendered PK. To validate the model's
logic (PK uniqueness, row counts) without building the parent, run its compiled
SQL (`target/compiled/...`, refs already prod-resolved under `--favor-state`)
against prod via the BQ MCP.

### `dbt clone` behavior on BigQuery

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

**A stale `--state` manifest makes the clone skip models silently, and a stale
`dbt_packages/` is why the manifest goes stale.** Symptom: a `--target staging`
build right after a full clone fails
`Not found: Table zz_stg_<district>_<source>.<model>` for a model that plainly
exists in prod. Cause chain: `dbt clone` skips any node absent from `--state`
(see above), and the prod manifest only regenerates via `.git/hooks/post-merge`
— which fails **silently** if `dbt parse` errors, freezing the manifest at its
last good date. The parse error is usually a package the project no longer
lists: a retired `local:` package stays in `<project>/dbt_packages/`, so parse
still loads its models and dies on one referencing a since-disabled model (e.g.
kippmiami kept a `powerschool` copy after the Focus migration →
`int_powerschool__contacts` → `stg_powerschool__studentcontactassoc` "is
disabled"). Diagnose by comparing the manifest's mtime to the model's add date
and `grep` for the node's `unique_id`; fix with
`dbt deps --project-dir src/dbt/<project>` (prunes the stale package) then the
`dbt parse --target prod --target-path target/prod` regeneration above.
Re-running the clone against the stale manifest just skips the same models
again.

### `dbt build --empty` destroys your dev relation contents

`--empty` doesn't just skip reading upstreams — it rebuilds every SELECTED
relation as `limit 0`, so a `--empty` run over `<model>+` leaves the whole
descendant graph EMPTY in your dev schema. A validation query run afterwards
returns 0 rows and looks like catastrophic row loss in the model.

Order matters: run validation queries BEFORE the `--empty` gate, or rebuild
without `--empty` afterwards. Distinguish this from a real break by checking a
relation OUTSIDE the `--empty` selection — a source copy that still has rows
while every selected model is 0 is the signature. Verified this session: a
409-node `--empty` gate zeroed `int_students__student_enrollments`,
`int_focus__advisory` and the `base_` passthrough while the unselected
`zz_<user>_kippnewark_powerschool` source kept its 97,855 rows.

### Stale dev tables shadow `--defer`

`--defer` uses any existing dev table before falling through to prod, so a stale
dev parent dim produces false-positive `relationships` orphans. Before trusting
a dev relationships warning on a FK, include the parent in `--select` or
`dbt clone --select <parent_dim>` from prod.

The inverse also happens: a stale dev CHILD makes a `relationships` test pass
VACUOUSLY. A `dbt test` that passes locally and warns in CI with thousands of
orphans is this, not a regression — confirm by holding the child fixed and
swapping only the parent.

Same trap applies to mart PK `unique` tests — a stale dev parent fans out a
date-range join. Query prod before filing upstream bugs or adding defensive
dedupe from a dev mart-test failure.

A stale dev copy missing a NEW column breaks the BUILD too ("Name <col> not
found inside <alias>"), not just relationships tests.
`dbt build --favor-state --defer --state <prod>` resolves every unselected
upstream to prod regardless of stale dev copies — cleaner than enumerating
parents in `--select`.

Conversely, to validate a consumer of a NEW column on an unmerged upstream,
`--select` BOTH: `--favor-state` resolves the unselected upstream to prod (which
lacks the column) and the consumer build fails; selecting the upstream builds it
into dev with the column first.

A re-run with a NARROWER `--select` invalidates a prior parity comparison:
`--favor-state` re-points every unselected upstream to prod, so a model you
changed earlier silently reverts to its prod definition and the dev-vs-prod
counts diverge for reasons unrelated to your edit. Re-validate with the SAME
full selection, or the delta is an artifact. Confirm which schema a dev view
actually reads via `INFORMATION_SCHEMA.VIEWS.view_definition`.

Also manifests as false row-count / row-presence deltas (not just
`relationships`/PK tests): a stale dev `int_people__staff_roster` missing recent
hires makes a dev-built rpt look like it dropped rows. Confirm which upstreams
resolved to dev by grepping the compiled SQL (`target/compiled/.../<model>.sql`)
for `zz_<user>_` refs — dev-schema refs mean `--defer` was shadowed; validate
against prod (or an ad-hoc prod query) instead.

**`--favor-state` governs refs, NOT `source()`.** kipptaf `sources-kipp*`
resolve to personal `zz_<user>_*` copies under `target=dev`, so a stale personal
copy fakes a dev-vs-prod delta that no flag corrects — this produced a phantom
7,000-row "regression" twice in one session. Validate a filter or union change
against the SOURCE rows the build actually read (query the `zz_<user>_*` table
directly), never against prod. Exception: a frozen BQ-native source (e.g.
`kippmiami_powerschool`) resolves to PROD even under `target=dev` — the opposite
staleness expectation from its district siblings.

To validate a MODIFIED `rpt_`/view against prod (the deployed view is still the
OLD code, and a dev build is stale-shadowed), rewrite its compiled SQL
(`target/compiled/.../<model>.sql`): `zz_<user>_` refs → prod schemas, and
inline any `stg_` you changed from its `source()` (prod lacks the new column);
run via `bq`. Tell live drift from a real logic change with distinct-key counts
(`total - dup`) vs a FRESH same-moment prod baseline — an unchanged distinct set
means the row delta is fan-out/drift (warehouse tables rematerialize
mid-session), not your change.

### Counting package-variant models enabled in a consuming district

`dbt ls --select "path:models/sis/staging/<variant>"` returns **0** in a
consuming district — the variant's models live in the _package_ dir, not the
district's `models/` path, so `path:` (relative to the project-dir) misses them.
Count with
`dbt ls --resource-type model --output path | grep 'sis/staging/<variant>/'`. A
package's own `dbt_project.yml` `+enabled: false` (models AND sources) applies
to every consumer — no per-district override needed (see the powerschool
odbc/sftp variants).

### `dbt ls --output json` stdout is mixed

Stdout interleaves dbt log lines with JSON records. Pipe through `grep '^{'`
before parsing.
