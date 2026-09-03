---
paths:
  - "**/src/dbt/**/models/**"
  - "**/src/dbt/**/tests/**"
---

# dbt model lifecycle

Loads on the first read under any dbt project's `models/` or `tests/`. Rules
that apply whether you are in the SQL or the YAML: layer requirements, moving,
retiring, rematerializing, and cross-project column changes. SQL-only rules are
in `.claude/rules/dbt-sql.md`; YAML-only rules in `.claude/rules/dbt-yaml.md`.

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

### Moving a model between directories changes its inherited config

`git mv` of a model silently re-parents it to a different `dbt_project.yml`
config tree — `+schema` (its BigQuery dataset) and `+contract` most often. A
move into `extracts/` or `marts/` newly ENFORCES the contract, so the properties
yml needs a complete column list with `data_type` or the build fails. Diff both
config blocks before the move, and rename the model's singular tests and their
`tests/properties.yml` entries with it.

### View→table flips for BigQuery plan depth

**Before re-attempting a materialization or automation-condition change, check
whether it was already reverted**:
`git log -S '<config key>' -- <properties yml>`. A reverted perf change reads as
an obvious win and CI passes for a while — that is how #4464 got re-done here,
eight days after #4587 reverted it.

A table model with a plan of hundreds of stages (straggler-fragile, e.g.
[#4153](https://github.com/TEAMSchools/teamster/issues/4153)) usually inherits
the depth from view upstreams: BigQuery inlines each view's full SQL per
reference, recursively — a view ref'd 4x expands 4x. Check upstream
materializations before flattening SQL. When flipping views to cron tables:

- Map EVERY consumer's refresh cadence first (exposure `cron_schedule`, Dagster
  schedules). An intraday consumer (hourly ops dashboard, 5x/day DDI suite)
  vetoes a nightly-cron table — leave that view a view.
- Give the whole flipped chain the SAME `automation_condition.cron_schedule`
  tick as its downstream — the `~any_deps_in_progress` guard serializes the pass
  (upstreams build first); no stagger needed.
- A properties-yml-only flip does NOT fire `code_version_changed` at deploy
  (`code_version` is a SHA1 of raw SQL). The relation stays a view until the
  first cron tick — don't judge the deploy by BigQuery object types.

### Table→view materialization conversion needs a drop

`create or replace view` does not drop a pre-existing table at the same path —
the conversion silently keeps serving the stale table. Ship table→view
conversions with either an explicit
`DROP TABLE IF EXISTS <project>.<dataset>.<model>` at deploy time, or run
`dbt build --select <model> --full-refresh` once after merge.

### Snapshot meta-column config changes need a manual DDL migration

Adding `hard_deletes: new_record` (or renaming meta columns via
`snapshot_meta_column_names`) to an EXISTING snapshot fails EVERY run with
`Snapshot target is missing configured columns` — dbt validates the target's
columns and raises before any merge; it never adds them
(`dbt/adapters/base/impl.py::assert_valid_snapshot_target_given_strategy`). Ship
the one-time DDL with the config change, handed to the user (BQ MCP is
SELECT-only): `alter table <snapshot> add column dbt_is_deleted string`, then
`update <snapshot> set dbt_is_deleted = 'False' where true` — dbt writes the
literal strings `'True'`/`'False'`, and the merge inserts by column name, so
append-at-end is fine. Never `--full-refresh` a snapshot to clear the error;
that destroys its SCD history.

### Column-rename refactors strand dependent prod views

When a staging column is dropped or renamed and a downstream view's SQL is
updated in the same commit, Dagster's auto-materialize may select only the
staging asset for the deploy run, leaving dependent prod views with their old
stored definition. BigQuery validates view SQL at read time, so every
`relationships` / `unique` test on the staging model fails with
`Name <col> not found inside <alias>; failed to parse view ...`. Confirm the
stored SQL is stale via `INFORMATION_SCHEMA.VIEWS.view_definition`, then
rematerialize each dependent view through Dagster `launch_run` — not a code
change.

### `dbt_utils.union_relations` is compile-time

Compiles to the column SUPERSET from source-table `INFORMATION_SCHEMA.COLUMNS`,
null-filling absent columns with `cast(null as <type>)`
(`dbt_utils/macros/sql/union.sql`). It needs persisted relations, so it cannot
union a local CTE — for that, BigQuery `full union all corresponding` gives the
same superset/null-fill semantics. New columns added at package-level staging
don't surface at kipptaf-level consumers until district projects rebuild prod.
For single-PR refactors, add transformations at the kipptaf-level wrapper, not
at package level.

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

A value-only change that alters a value's **format** (e.g. raw phone → E.164) is
schema-safe but can silently break downstream extracts with positional / format
assumptions — the shared `int_finalsite__student_contacts` E.164 change broke
`rpt_clever__students`' `left(regexp_replace(phone, '\W'), 10)` (it truncated
the 11-digit `+1…`). Before reformatting a value at a shared model, grep
consumers for `left(` / `substr(` / digit-count assumptions on that column — CI
won't catch it (compiles fine; no error).

A doc-only inline SQL comment on a heavily-consumed intermediate still marks it
`state:modified`, fanning CI's `state:modified+` rebuild across its whole
descendant graph and surfacing unrelated pre-existing warn-tests as noise. Put
documentation notes in the properties `description` (doesn't mark modified), not
an inline SQL comment, on hub models.

**Validating a NEW union wrapper locally**: the column list resolves at compile
from the source relation's `INFORMATION_SCHEMA`, so a dev-target compile expands
to nothing — the `zz_<user>_*` dataset holds no copy.
`dbt compile --select <wrapper> --target staging` resolves against the same
`zz_stg_*` relations dbt Cloud CI reads, and is not a warehouse write so it
needs no authorization. Read the compiled SQL to confirm columns were listed; an
empty expansion still compiles clean.

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

**Exception** — thin cross-project wrapper `rpt_` models (a district
`rpt_powerschool__autocomm_*` or other `extracts/` wrapper sourcing
`kipptaf_extracts`) are contract-columns-only: NO uniqueness test or
descriptions, which live on the kipptaf source view. See `kipptaf/CLAUDE.md` →
`extracts/powerschool/` special case before adding either.

### Retiring a crosswalk or lookup as redundant

Check the join TYPE per consumer first. An INNER join makes the table a
membership filter — often gating an outbound feed — not a lookup, and its row
set may encode no derivable rule. Likewise count the rows any replacement
`coalesce` fallback actually fires on: one written to preserve a single row
fired on 251.

### Retiring a model is always a disable, never a delete

Set `config: enabled: false` in the properties yml and leave the `.sql` and the
prod relation in place. Applies even when the model has no exposure and zero
remaining `ref()`s — a consumer nobody knew about then degrades to frozen data
instead of vanishing. Do not propose deletion as the tidier option, and do not
issue a `drop view` for the orphaned relation. Disabling a model does NOT
disable its tests (see _Test config defaults_ in `.claude/rules/dbt-yaml.md`) —
add `enabled: false` to each of those too.

### Verifying a test-removal PR

Never report a count from the YAML diff — it does not say which dbt nodes
actually disappeared. `dbt parse` on main and on the branch, then diff the
`resource_type == 'test'` node names. That fixes the delta and proves nothing
unintended was dropped.

Parse BOTH sides with `--no-partial-parse` — partial parse caches node
enable/disable state and under-reports (767 vs 772 tests this session). Re-parse
main fresh too: the main checkout's manifest is a stale artifact that reports
since-deleted models as REMOVED and since-added ones as ADDED.

### Flattened child-array model naming

`<layer>_<source>__<parent>__<child>` — `stg_coupa__users__roles`,
`int_deanslist__incidents__actions`, `int_focus__users__pivot`.

### Legacy `base_` prefix

Existing `base_` models are being renamed to `int_`
([#2541](https://github.com/TEAMSchools/teamster/issues/2541)). Do not create
new `base_` models.
