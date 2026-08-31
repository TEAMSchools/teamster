# CLAUDE.md — `dbt/kipptaf/`

The **network-wide analytics project** — aggregates all source-system packages
and four district projects into network-level marts, reporting, and extracts.

## Model Structure

```text
models/
  <source>/          # per-integration (adp, deanslist, powerschool, etc.)
    staging/         # table, contract enforced
    intermediate/
  assessments/       # cross-source assessment aggregations
  people/            # unified staff/HR (ADP + LDAP + PS + perf mgmt, has snapshots)
  students/          # cross-school student data
  marts/             # dim_*/fct_* for Tableau + Cube semantic layer, contract enforced
  reporting/         # topline reporting (+schema: reporting, no contract defaults)
  extracts/          # outbound feeds, contract enforced
    tableau/         # +schema: tableau → lands in kipptaf_tableau
    deanslist/
    powerschool/     # see note below
    google/
  exposures/         # dbt exposures (Tableau, Google Sheets, etc.)
```

## Source File Conventions

Each integration uses two source files with the **same `name:` under
`sources:`** (dbt merges at parse time):

| File                   | Points to                          | Schema expression                    |
| ---------------------- | ---------------------------------- | ------------------------------------ |
| `sources-external.yml` | GCS Avro / Google Sheets externals | dev-prefixed (env-isolated)          |
| `sources-bigquery.yml` | Native BQ tables (Airbyte, frozen) | plain hardcoded (e.g. `kipptaf_foo`) |

When both files exist for the same source, `sources-bigquery.yml` omits
`schema:`.

**Archive pattern**: Disable the model (`config: enabled: false` in properties
YAML) → add BQ-native entry in `sources-bigquery.yml` → update downstream
`ref()` → `source()`. Examples: `google/sheets/sources-bigquery.yml`,
`performance_management/sources-bigquery.yml`.

**Shared-spreadsheet risk**: Google Sheets sharing a URI all trigger together on
any tab change. Archive tabs must be converted to BQ-native sources.

## Key Rules

### Cross-region joins (critical)

Union models carry `_dbt_source_relation` but values differ across models (they
include schema + table name). **Never join on
`a._dbt_source_relation = b._dbt_source_relation`** — join the materialized
`_dbt_source_project` column:

```sql
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and a._dbt_source_project = b._dbt_source_project
```

The `union_dataset_join_clause` macro that wrapped this comparison was deleted
in [#3142](https://github.com/TEAMSchools/teamster/issues/3142). Five stale
calls remain in the disabled pre-AY2627 gradebook-audit cluster
(`int_tableau__gradebook_audit_assignments_teacher` / `_categories_teacher` /
`_assignments_student`). Disabled models are never compiled, so the calls are
inert — but re-enabling any of those models means swapping them first.

Produce `_dbt_source_project` on a union model with
`select *, {{ extract_source_project() }} as _dbt_source_project`
`from union_relations` (the `union_relations` CTE wrapping
`dbt_utils.union_relations`).

Prefer inline `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` over the
`extract_source_project` macro when the union view is `select *` with an `AM04`
trunk-ignore, or is mocked in a dbt unit test: the macro form makes AM04 stop
firing (`trunk/ignore-does-nothing`), and its table-name qualifier breaks unit
tests (`Unrecognized name` after dbt renames the mocked ref). Siblings
`stg_powerschool__courses` / `stg_powerschool__studentcorefields` use inline.

### `_dbt_source_relation` does not always encode region

`_dbt_source_relation` from `union_relations` encodes whatever the union is OVER
— it is region ONLY for cross-district unions (`kipp<region>_<source>`). Unions
over years / repository ids / sftp-vs-api method / current+archive (illuminate,
zendesk, `stg_schoolmint_grow__generic_tags`, amplify mClass) are NOT region, so
the region regex `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` yields
null — keep them out of `_dbt_source_project` joins. Shared NJ schemas
(`kippnj_iready`, `kippnj_renlearn` for STAR) prefix `kippnj` ≠ home region;
resolve region from `int_people__location_crosswalk`, not the regex.

### `_dbt_source_project` is pass-through, derived only at the union view

`extract_source_project()` (the `regexp_extract`) belongs ONLY on the
`union_relations` view that creates `_dbt_source_relation`. Every downstream
join-target selects the materialized `_dbt_source_project` column THROUGH from
its upstream producer — never re-derive it downstream.

- **Snapshot-fed models are the exception — they derive** from
  `_dbt_source_relation`: the snapshot doesn't carry `_dbt_source_project` (e.g.
  `snapshot_powerschool__gpa_term`, whose source
  `int_powerschool__gpa_term_current` re-selects columns and drops it), and
  adding it to the snapshot's source model leaves it ~99% NULL — the `check`
  strategy only backfills touched rows.
- Adding the column to a (non-contracted) intermediate still needs a
  `properties.yml` column entry
  (`description: District code location derived from _dbt_source_relation.`) —
  the doc convention applies regardless of contract enforcement.

### Selecting from `dbt_utils.star()` models

`base_` models using `star()` resolve columns from BigQuery at run time, not
SQL. YAML properties drift silently. **Rule**: enumerate columns explicitly when
joining these models (see `INFORMATION_SCHEMA.COLUMNS` query in
`src/dbt/CLAUDE.md`).

`union_relations` views have a related issue (stale compiled SQL) but are
handled automatically by `dbt_union_relations_automation_condition()`.

### kipptaf-level `stg_*` union views

Pure `union_relations()` views over per-region district staging tables (e.g.
`stg_powerschool__u_studentsuserfields`, `stg_powerschool__studentcorefields`)
are functionally intermediates. Uniqueness tests and `materialized: table`
belong on the per-region source-system staging models, not on the kipptaf-level
view. Don't add either when creating a new one.

Contract-enforcement here is per-model, NOT directory-wide: the `powerschool:`
block in `dbt_project.yml` sets only `+schema:` (no `staging: +contract`), so
powerschool `staging/` union views are contract-enforced only where a model sets
it in its own `properties.yml` (e.g. `stg_powerschool__users`,
`stg_powerschool__log`). Check the model's `properties.yml` before assuming a
`select *` union view is or isn't contracted.

### Exposing a package/district model as a kipptaf source

Every source added to a `sources-kipp*.yml` needs a matching kipptaf
`union_relations` passthrough model. Consumers read the wrapper, not the source.

Surface DECODED views, never the lookup tables behind them. Exposing a decode
crosswalk (e.g. focus `int_focus__custom_field_options`) relocates hand-rolled
translation into kipptaf instead of removing it; a field a package `__pivot`
misses gets added to that pivot, in the package.

`config.meta.contains_pii` does NOT travel through `source()` — a wrapper over a
PII-tagged package model must re-declare it. Model level suffices for a
`select *` passthrough, whose column docs live on the source model.

### Finalsite contact unions

`int_finalsite__student_contacts` / `int_finalsite__contact_id_attributes` /
`int_finalsite__student_address_of_record` /
`int_finalsite__contact_address_of_record` are kipptaf `union_relations` views
over per-region finalsite sources.

- **Union CUTOVER regions, not merely api-enabled ones.** Miami has the
  finalsite api enabled with contacts data AND `powerschool_student_number`s, so
  unioning it into `int_finalsite__student_contacts` double-counts against the
  PowerSchool branch of `int_students__contacts` (the grain test catches it).
  `int_finalsite__contact_id_attributes` and
  `int_finalsite__student_address_of_record` DO include Miami — Focus consumes
  them, and the `rpt_focus__*` filter `focus_student_id_prefixed is not null`,
  so Newark rows (null prefix) never reach the Focus feeds.
- **Source schema staging branch**: all four regions' finalsite sources
  (`sources-kippmiami.yml`, `sources-kippcamden.yml`, `sources-kippnewark.yml`,
  `sources-kipppaterson.yml`) carry the `staging`→`zz_stg_` branch (single-PR
  pattern — a cross-region finalsite union needs the staged copies for CI).
  Newark gained it in #4400 (DeansList contacts) alongside a column add to
  `int_finalsite__student_contacts`; before pushing any finalsite column-adding
  PR, seed the staged copies per district (`dbt clone --target staging` +
  `dbt build --select <model> --target staging`) so CI's union-wrapper rebuild
  sees the new columns.

### `extracts/powerschool/` special case

`rpt_powerschool__autocomm_*` models define a shared export format but are
**not** extracted here — regional projects source from them, filter to their
data, and push to their own PowerSchool instance. Exposures live in regional
projects, not kipptaf.

This cross-project shape generalizes (e.g. finalsite→focus,
`extracts/parentsquare/`): the heavy `rpt_*` view lives in kipptaf sourcing
district data via `source()`, and each district has a thin wrapper sourcing
`kipptaf_extracts`. The wrapper is contract-columns-only — NO data tests or
descriptions (those live on the kipptaf view). A new kipptaf region source
(`sources-kipp*.yml`) needs the `dev`/`staging` (`zz_stg_`)/prod schema branch,
or single-PR cross-project CI can't read it.

**The wrapper's region filter is a `code_location` column** the kipptaf view
exposes (`_dbt_source_project as code_location`, or the roster's
`home_work_location_dagster_code_location` for staff feeds) — the wrapper then
filters `where code_location = '{{ project_name }}'` and does NOT project it.
Don't expose `_dbt_source_project` under its own name for this; `code_location`
is what `rpt_powerschool__autocomm_students` and `rpt_parentsquare__*` use.

**Widening a Newark-only view to NJ is not just a filter swap** — a bare
`cross join` to schools fans a region's staff across every NJ school, and an
ungrouped `min()` pick over a sibling feed assigns one owner network-wide that
dangles in every other region's file while a single-column `relationships` test
still passes. Region-key both, and check school-number / `student_number`
collisions and enum-domain tests (e.g. grade level) against prod before
implementing, since widening changes the population every error-severity test
runs over.

**finalsite→focus exception**: the kippmiami `rpt_focus__*` are NOT thin
pass-throughs — they are the reconciliation layer (import-once / diff against
current Focus via the `focus` package, which only kippmiami has). kipptaf
`rpt_focus__*` are desired-state (all rows); the **kippmiami** output is the
actual SFTP feed. Per feed: addresses/contacts/demographics import-once
(presence anti-join, with a null/street-line gate #4320); enrollment diffs and
additionally reads Focus in kipptaf via a BQ-native source (#4319). Spec:
`docs/superpowers/specs/2026-06-29-finalsite-focus-idempotent-imports-design.md`.

## Reuse existing entity identity

**Before deriving an entity key in a new model, grep the marts.**
`dim_student_contact_persons` and `bridge_student_contacts` already define
`person_identity` and `student_contact_person_key`; an extract that invents its
own contact key silently disagrees with them. A shared identity expression
belongs in the `int_` model every consumer reads, not copy-pasted per consumer.

## `dbt_project.yml` Inherited Defaults

These are set at directory level — **do not repeat per-model** or flag their
absence:

| Directory / pattern                    | `materialized` | `contract: enforced` |
| -------------------------------------- | -------------- | -------------------- |
| All integration `staging/`             | `table`        | `true`               |
| `extracts/`                            | view (default) | `true`               |
| `marts/`                               | view (default) | `true`               |
| `illuminate/dlt/staging/repositories/` | `table`        | `false` (override)   |

The `repositories/` contract override is deliberate — the unpivot macro reads
columns at parse time, so they cannot be declared. See
`models/illuminate/CLAUDE.md` for that, the disabled repository list, and the
`fivetran/`-is-dead warning.

**Disabled integrations** (project-level `+enabled: false`): ACT, ADP Workforce
Manager, ADP Workforce Now Fivetran, Alchemer, Coupa Fivetran, Dayforce,
Facebook, Illuminate Fivetran, Instagram.

**`partition_by` on a Cube-read mart is a no-op on its own.** Cube compiles a
date filter routed through the `dates` join into a predicate on `dim_dates`, and
BigQuery cannot prune a fact's partitions from a predicate on a joined table.
The partition only pays off paired with a fact-side time dimension the view's
description sends date filters to — `fct_student_days`
(`PARTITION BY DATE_TRUNC(date_key, MONTH)`) with `student_days.attendance_date`
is the worked example. Pick monthly over daily for a multi-year daily-grain
fact: 7,058 distinct dates already, so daily passes BigQuery's 4,000-partition
cap inside a decade. See `src/cube/CLAUDE.md` for the measurements and the
Cube-side rule.

## Known Upstream Issues

**Miami is the exception, deliberately.** Focus is Miami's sole enrollment
source and has no placeholder equivalent, so the Focus cutover removed Miami's
1,002 placeholder rows (420 students, AY2022-AY2025) — from the spine in #4775
and from `base_powerschool__student_enrollments` in #4868. The
retain-graduate-placeholder rule below still binds the three NJ regions. Do not
"restore" Miami placeholders by reviving the frozen archive branch; that was
decided against on 2026-08-14.

**Point-in-time enrollment headcount uses entry/exit dates, not
`enroll_status`.** `count_students` on the `student_days` Cube counts distinct
students over whatever slice is queried. There are no anchor measures and no
anchor columns — pin `dates_date_day` to a date for a point-in-time figure,
leave it open for ever-enrolled over a range. `fct_student_days` carries a row
for every calendar day inside a stint, break days included, so any date resolves
for every school.

**Each stint's day window is clamped to its school's academic year, and that
clamp is load-bearing.** PowerSchool rolls NJ stints over on 1 July while Focus
dates Miami stints to the real first day of school (19,979 Newark July entries
against 2,955 Miami August entries, AY2024-26). An unclamped window would report
Newark at roughly 20,000 students in mid-July against almost no Miami students,
purely from a source-system date convention. Clamping to the school year makes
any calendar date comparable across regions; mid-July correctly returns nobody
anywhere.

**Miami is present across history on `fct_student_days`.** Its rows come from
`int_extracts__student_enrollments` × `int_students__calendar_day`, and both
retain Miami — the calendar keeps the frozen PowerSchool archive for the years
Focus does not cover. Miami _attendance_ before AY2026 is still absent (#4803
dropped that archive, and every Tableau attendance surface has the same gap), so
those rows carry null attendance. Every rate already excludes null attendance
from both numerator and denominator (#4744), so the gap cannot move a network
rate — and Focus historical attendance, if it is ever modelled, fills in with no
change to these models. Paterson `attendance_value` is unreliable (upstream PS
conversion-items gap, #4193) but `membership_value` is clean, so enrollment
counts include Paterson correctly.

**School calendars diverge at year-end; never anchor a point-in-time count on a
network-wide `max(date)`.** Mid-year months share a last in-session day across
schools, but June does not (Miami ends ~Jun 4, Newark ~Jun 9, others to ~Jun
29). Any "as of the last day of the period" computation (year/month/week-end)
must take the per-school last in-session day
(`max(date_value) ... group by school`), capped at `current_date` for the
in-progress period — a global max silently drops early-ending schools (e.g. all
of Miami).

Model and column semantics for these live in each model's properties yml. What
stays here is what to do and what not to do.

- **`stg_powerschool__students`** — never resolve identity or attribute facts
  against `enroll_status` `-1` or `1`. Apply the `dcid >= 1` placeholder filter
  when reading a per-region staging table directly.
- **`int_powerschool__student_enrollment_union`** — retain graduate placeholder
  rows; derived enrollment models and `dim_student_enrollments` stay
  alumni-inclusive. Include `academic_year` in surrogate key inputs.
- **`stg_powerschool__cc` double-writes** — filter `is_dropped_section` first
  when date-range joining `base_powerschool__course_enrollments`. Do NOT add
  defensive dedupes (`qualify row_number() = 1` or `dbt_utils.deduplicate()`)
  for the residual fan-out. Downgrade the affected mart PK uniqueness test to
  `severity: warn` with a `TODO(#3915)` so it returns to error when source
  cleanup completes. `base_powerschool__student_enrollments` date-range joins
  currently need no tiebreaker. Tracked in
  [#3900](https://github.com/TEAMSchools/teamster/issues/3900); Ops cleanup in
  [#3915](https://github.com/TEAMSchools/teamster/issues/3915).
- **`int_people__location_crosswalk`** — consumers joining on an aliased name
  (e.g. `fct_staff_observations` on `gro.school_name`) must use this model.
  Canonical-grain consumers, meaning one row per logical school, use
  `stg_google_sheets__people__locations`.
- **`stg_google_sheets__people__campus_crosswalk`** — do not reintroduce a
  `Campus_Name` scalar on the locations sheet.
- **`stg_google_sheets__people__locations`** — to map `_dbt_source_project` to a
  region, use `dim_regions.dagster_code_location`, not this model.
- **SchoolMint Grow archived rows** — `stg_schoolmint_grow__measurements` and
  `stg_schoolmint_grow__rubrics__measurement_groups__measurements` deliberately
  do not filter to non-archived. Don't re-add the filter to those two without
  understanding the FK-coverage tradeoff.
- **`dim_staff`** — do NOT filter
  `dim_work_assignment_status.status_name != 'Terminated'` to get "active". That
  field is misaligned with the roster's `worker_status_code` and over-drops
  roughly 100 roster-active staff. The roster active-and-primary set (~1,526)
  runs ~30 larger than the marts' current-primary set, from hire and termination
  timing. On the `rpt_tableau__*` extracts, `entity` (KTAF vs Region) derives
  from `business_unit_name` — `KIPP TEAM and Family Schools Inc.` is KTAF,
  anything else is Region.
- **`stg_renlearn__star`** — `int_renlearn__star_rollup` is disabled
  (`config: enabled: false`); leave it. Edit and consume STAR at
  `stg_renlearn__star`.
- **`stg_adp_workforce_now__workers` ghosts** — fix by rematerializing the ADP
  `workers` partitions spanning the record's active dates; the re-pull drops the
  ghost and downstream tables rebuild via automation. Detection check tracked in
  [#4407](https://github.com/TEAMSchools/teamster/issues/4407).

## Exposures

Every external consumer **must** have a dbt exposure in `models/exposures/`.
Files grouped by tool: `tableau.yml`, `google-sheets.yml`, etc.

Required fields: `name`, `label`, `type`, `owner.name: Data Team`, `depends_on`,
`url`, `config.meta.dagster.kinds`.

**Tableau workbooks** — add `asset.metadata.id` (LSID) when known. Add
`cron_schedule` only if Dagster owns the refresh:

```yaml
config:
  meta:
    dagster:
      kinds: [tableau]
      asset:
        metadata:
          id: <lsid-uuid> # always include if known
          cron_schedule: "0 7 * * *" # only if Dagster-managed
```

These crons become real Dagster refresh schedules
(`code_locations/kipptaf/tableau/schedules.py`) and set the freshness floor for
upstream cadence decisions — check them before moving an upstream model to a
cron automation condition (see `src/dbt/CLAUDE.md` → View→table flips).

## kipptaf-Specific Variables

`bigquery_external_connection_name`:
`projects/teamster-332318/locations/us/connections/biglake-teamster-gcs`

dbt Cloud project ID: `211862`.

## dbt Cloud CI

CI job: `dbt build --select state:modified+ --full-refresh`, target `staging`,
defers to Staging environment.

A refactor touching many models pulls them into `state:modified+`, so CI builds
models it has never built — expect latent `severity: error` failures unrelated
to your change (a 56-file sweep surfaced 5 duplicate PKs sitting in prod). Query
prod for the same count before assuming you caused it, and budget for triage
when scoping a wide sweep.

`state:modified+` is branch-vs-deferred-environment, NOT commit-vs-commit. A
docs-only or `.md`-only push to a branch that already modifies dbt models
re-runs the whole selection — measured at 918 relations and ~4.5 min on a
13-file PR whose last commit touched only `.md`. Batch doc commits before
pushing, or land them in a separate PR. Verify what a run actually built with
`creation_time` in `region-us.INFORMATION_SCHEMA.TABLES` filtered to
`dbt_cloud_pr_<job>_<pr>%` — step duration and warning counts are both weak
proxies.

CI is scoped to the kipptaf project only. PRs touching only a district project
(kipppaterson, kippnewark, kippcamden, kippmiami) get a no-op kipptaf CI run
that selects no models — kipptaf CI green is not evidence the district-side
changes are correct. Verify via local `uv run dbt build` against the district
project.

`Clone - Staging (Modified)` clones only `state:modified` models, not their
parents. When CI fails on a stale staging defer table for an unmodified upstream
(column missing after a recent merge), trigger the full `Clone - Staging` job —
or `dbt clone --select <upstream>` against staging. Trigger via
`mcp__dbt__trigger_job_run` with the `Clone - Staging (On-Demand)` job ID from
`mcp__dbt__list_jobs` (~5 min run); after success, empty-commit + push
re-triggers Build - CI.

`Clone - Staging` refreshes only kipptaf-level relations — NOT district-level
`zz_stg_kipp<district>_*`. A CI orphan / row-count delta that reconciles exactly
against per-district prod-vs-`zz_stg` gaps is that staleness, not your change;
re-running Clone - Staging won't fix it.

Distinct from stale staging defer — **stale per-PR shadow**: a model that was
`state:modified` in an earlier run (e.g. before the branch merged `main`) but is
now unmodified leaves a stale copy in the per-PR schema
(`dbt_cloud_pr_<job>_<pr>_<schema>`, one dataset per dbt custom schema). dbt
prefers an existing same-schema relation over the staging defer, so consumers
fail `Name <col> not found` even when `zz_stg_*` has the column. Confirm via
`INFORMATION_SCHEMA.COLUMNS` on the per-PR vs `zz_stg_*` schema, then drop the
stale per-PR relation (match `drop view`/`drop table` to its type) — or
`drop schema ... cascade` the whole `dbt_cloud_pr_<job>_<pr>_*` set to avoid
model-by-model whack-a-mole — and re-run. Claude is DDL-blocked (BQ MCP / `bq`
are SELECT-only), so hand the drops to the user.

Re-triggering Build - CI: prefer `mcp__dbt__retry_job_run(run_id=<failed run>)`
— it retries the _existing_ run, keeping the PR-schema override
(`trigger_job_run` loses it; that's why the fallback is empty-commit + push).
But `dbt retry` replays the prior run's compiled SQL and re-runs only
errored/skipped nodes — so after changing external state (dropping PR schemas,
refreshing staging) use a fresh build (empty-commit + push), not retry.

## Single-PR cross-project workflow

CI only builds kipptaf; district staging schemas aren't auto-populated. For a PR
touching both a district model and a kipptaf consumer:

1. Add `target=staging` branch to affected `sources-kipp*.yml` (routes to
   `zz_stg_<district>_<source>`).
2. From each affected district project, run broad clone (no `--select`):
   `uv --directory <worktree> run dbt clone --target staging --state target/prod`
   to seed `zz_stg_<district>_*` from prod.
3. Push; CI reads staged regional via the schema branch.

`dbt clone` only seeds upstreams UNCHANGED in this PR (it copies prod schema).
For district/package models you MODIFIED, clone gives the OLD schema — instead
`stage_external_sources --target staging` their externals, then
`dbt build --select <model> --target staging` into `zz_stg_`. Also clone+build
`zz_stg_kipptaf` itself — under `--target staging` kipptaf reads its own models
from there. Seed EVERY district that unions into the kipptaf model (e.g.
`kipppaterson`, which feeds `stg_pearson__njsla`/`_science` via its own
`int_pearson__*`, not the package `stg_*`).

Alternative to the two-PR pattern in `src/dbt/CLAUDE.md`.

## Stale-wide `zz_stg` union defer copy

When a kipptaf `union_relations` wrapper's `zz_stg` defer copy is wider than
current (e.g. a district lags a column-drop rollout, so the prod-cloned copy
still carries the dropped column), rebuild the wrapper `--target staging`:
`union_relations` recomputes the column intersection from the CURRENT district
`zz_stg` sources, yielding a corrected (narrow) copy — no prod rematerialization
and no waiting on the lagging district. Used to unblock CI on a downstream
consumer that fails on the stale wide column.

## Verifying a coalesce/override layer is vestigial

Compare the override source against the **raw upstream**, not the
already-coalesced output column. `coalesce(override, raw)` trivially matches
`override` when it fires; comparing resolved-to-override hides every real
override. Source the staging model that feeds the coalesce, not the intermediate
that applies it.

Concretely: compare `stg_x.raw_col` (the staging input feeding the coalesce)
against `int_x.override_col` (the override source), not `int_x.resolved_col`
(the post-coalesce output).

A source id can also be reported inconsistently across loads (e.g. Pearson
`localstudentidentifier` arriving as either the legacy district id or the KIPP
`student_number`), so a translation that looks like a no-op in today's data may
be load-bearing for other loads. Verify across the value domain — not one
snapshot — before removing it.

## Model Layer Distinctions

- **`rpt_`** — analyst-built reporting views for external tools. Live in
  `models/extracts/`.
- **`dim_*` / `fct_*`** — dimensional marts for semantic layer. Live in
  `models/marts/`. Actively being developed; see
  `src/dbt/kipptaf/models/marts/CLAUDE.md` for column-naming rubric, hash-change
  discipline, and strict-chain rules.

New KIPP Forward Google Sheets extracts take the `rpt_gsheets__kfwd_` prefix.
Existing models use both `kfwd_` and `kippfwd_`; `kfwd_` is the going-forward
choice, and the older ones are not being renamed.
