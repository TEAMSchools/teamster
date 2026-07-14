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

### `union_dataset_join_clause` (critical)

Union models carry `_dbt_source_relation` but values differ across models (they
include schema + table name). **Never join on
`a._dbt_source_relation = b._dbt_source_relation`** — use the macro:

```sql
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and {{ union_dataset_join_clause(left_alias="a", right_alias="b") }}
```

Macro defined in `macros/utils.sql` — extracts school prefix via
`regexp_extract(..., r'(kipp\w+)_')`.

When both joined union models materialize `_dbt_source_project`, prefer
`a._dbt_source_project = b._dbt_source_project` over the macro — same semantics,
no `regexp_extract` per call.

Produce `_dbt_source_project` on a union model with
`select *, {{ extract_code_location("union_relations") }} as _dbt_source_project`
`from union_relations` (the `union_relations` CTE wrapping
`dbt_utils.union_relations`).

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

### Finalsite contact unions

`int_finalsite__student_contacts` / `int_finalsite__contact_id_attributes` are
kipptaf `union_relations` views over per-region finalsite sources.

- **Union CUTOVER regions, not merely api-enabled ones.** Miami has the
  finalsite api enabled with contacts data AND `powerschool_student_number`s, so
  unioning it into `int_finalsite__student_contacts` double-counts against the
  PowerSchool branch of `int_students__contacts` (the grain test catches it).
  `int_finalsite__contact_id_attributes` DOES include Miami — Focus consumes it,
  and the `rpt_focus__*` filter `focus_student_id_prefixed is not null`, so
  Newark rows (null prefix) never reach the Focus feeds.
- **Asymmetric source schema**: `sources-kippmiami.yml` finalsite carries a
  `staging`→`zz_stg_` branch (single-PR pattern, needs a staged copy for CI),
  while `sources-kippnewark.yml` is dev-only (staging→prod). A cross-region
  finalsite union pulls a `zz_stg` seeding dependency from Miami but reads prod
  for Newark — a Newark-only union is CI-safe without staging.

### `extracts/powerschool/` special case

`rpt_powerschool__autocomm_*` models define a shared export format but are
**not** extracted here — regional projects source from them, filter to their
data, and push to their own PowerSchool instance. Exposures live in regional
projects, not kipptaf.

This cross-project shape generalizes (e.g. finalsite→focus): the heavy `rpt_*`
view lives in kipptaf sourcing district data via `source()`, and each district
has a thin wrapper sourcing `kipptaf_extracts`. The wrapper is
contract-columns-only — NO data tests or descriptions (those live on the kipptaf
view). A new kipptaf region source (`sources-kipp*.yml`) needs the
`dev`/`staging` (`zz_stg_`)/prod schema branch, or single-PR cross-project CI
can't read it.

**finalsite→focus exception**: the kippmiami `rpt_focus__*` are NOT thin
pass-throughs — they are the reconciliation layer (import-once / diff against
current Focus via the `focus` package, which only kippmiami has). kipptaf
`rpt_focus__*` are desired-state (all rows); the **kippmiami** output is the
actual SFTP feed. Per feed: addresses/contacts/demographics import-once
(presence anti-join, with a null/completeness gate #4320); enrollment diffs and
additionally reads Focus in kipptaf via a BQ-native source (#4319). Spec:
`docs/superpowers/specs/2026-06-29-finalsite-focus-idempotent-imports-design.md`.

## `dbt_project.yml` Inherited Defaults

These are set at directory level — **do not repeat per-model** or flag their
absence:

| Directory / pattern                    | `materialized` | `contract: enforced` |
| -------------------------------------- | -------------- | -------------------- |
| All integration `staging/`             | `table`        | `true`               |
| `extracts/`                            | view (default) | `true`               |
| `marts/`                               | view (default) | `true`               |
| `illuminate/dlt/staging/repositories/` | `table`        | `false` (override)   |

**Disabled illuminate repositories**: 365, 413, 428 — disabled in
`models/illuminate/dlt/staging/repositories/properties.yml`. Check before adding
`ref()` calls to `int_illuminate__repository_data`.

**Disabled integrations** (project-level `+enabled: false`): ACT, ADP Workforce
Manager, ADP Workforce Now Fivetran, Alchemer, Coupa Fivetran, Dayforce,
Facebook, Illuminate Fivetran, Instagram.

## Known Upstream Issues

**`int_people__location_crosswalk`** is NOT a union model — it has no
`_dbt_source_relation`. Use `extract_code_location()` matched against
`location_dagster_code_location` for cross-region joins. Each row is one alias
(alternate spelling of `location_name`) — consumers that join on an aliased name
(e.g., `fct_staff_observations` on `gro.school_name`) must use this model.
Canonical-grain consumers (1 row per logical school) should use
`stg_google_sheets__people__locations` instead.

**`stg_google_sheets__people__campus_crosswalk`** uniqueness grain is
`Location_Name` only. `Name` is the parent campus and repeats across sibling
schools (e.g., `KIPP Miami - North Campus` rolls up five `Location_Name`
children).

**`stg_powerschool__students` phantom rows**: PowerSchool retains 4 placeholder
rows (one per district) with
`dcid = -100, student_number = 0, enroll_status = -100`. The kipptaf-level view
filters them via `where dcid >= 1`. Apply the same filter if reading a
per-region source-system staging table directly.

**`stg_powerschool__students` `enroll_status = 1` is invalid.** Filter
`enroll_status IN (0, 2, 3)` (active / withdrawn / graduated) when resolving
identity or attributing facts to a student. `-1` is pre-registered (not yet
enrolled); `1` is inactive — never report against either.

**`int_powerschool__student_enrollment_union` graduate placeholders**: rows with
`enroll_status = 3` have NULL `entrydate` / `exitdate`, one row per
`academic_year` per (student, district). `generate_surrogate_key` inputs that
include `academic_year` hash uniquely; omitting `academic_year` collides.
Date-range joins on `entrydate` silently drop these rows. Retain them for KIPP
Forward / kippadb alumni reporting — derived enrollment models must not drop
them, and `dim_student_enrollments` stays alumni-inclusive.

**`enroll_status` is student-level, not per-stint.** Sourced from
`stg_powerschool__students` and copied identically to every row in
`int_powerschool__student_enrollment_union`. Don't expect different stints for
the same student to carry different values. **For point-in-time or historical
enrollment counts, filter by enrollment dates (`entrydate`/`exitdate` covering
the target date), NOT `enroll_status`** — status is current-only, so a status
filter drops a mid-year withdrawal even from dates they were still enrolled
(~887 students network-wide for AY2025) and never reflects
status-on-a-past-date. Topline `Total Enrollment` counts by dates, not status;
match that for reconciliation.

**Point-in-time enrollment headcount uses entry/exit dates, not
`enroll_status`.** `count_students` in the `student_enrollments` Cube derives
from `fct_student_attendance_daily` anchored on per-school `is_current_record` /
`is_enrollment_month_end_record` / `is_enrollment_week_end_record`. Topline
Total Enrollment reconciles at Oct-1 2025 = 10,637 (Camden 2,161 / Miami 1,346 /
Newark 6,608 / Paterson 522). Break weeks (no in-session rows) return 0 by
design — gap-fill in the BI layer. Paterson `attendance_value` is unreliable
(upstream PS conversion-items gap, #4193) but `membership_value` is clean —
enrollment counts include Paterson correctly.

**School calendars diverge at year-end; never anchor a point-in-time count on a
network-wide `max(date)`.** Mid-year months share a last in-session day across
schools, but June does not (Miami ends ~Jun 4, Newark ~Jun 9, others to ~Jun
29). Any "as of the last day of the period" computation (year/month/week-end)
must take the per-school last in-session day
(`max(date_value) ... group by school`), capped at `current_date` for the
in-progress period — a global max silently drops early-ending schools (e.g. all
of Miami).

**`dim_terms.type` is KIPP-managed, not PowerSchool-derived.** Values from
`stg_google_sheets__reporting__terms` — RT (reporting term, quarter grain), ATT
(attendance, semester/year grain only), LIT, AR, REP, SURVEY, etc. Quarter
attendance rows live under `type='RT'` matching `term_name='Q1'..'Q4'` — NOT
`type='ATT'`, NOT keyed by `term_code='RT1'..'RT4'`.

**`base_powerschool__course_enrollments` PowerSchool double-writes**: a frozen
historical corpus of duplicate `cc` rows for the same
`(student, section, dateleft)`, surfaced by a warn-level
`dbt_utils.unique_combination_of_columns(studentid, sectionid, dateleft)` test
on `stg_powerschool__cc`. Tracked in
[#3900](https://github.com/TEAMSchools/teamster/issues/3900); Ops cleanup in
[#3915](https://github.com/TEAMSchools/teamster/issues/3915).

- When date-range joining `base_powerschool__course_enrollments`, filter
  `is_dropped_section` first.
- Do not add defensive dedupes (`qualify row_number() = 1` or
  `dbt_utils.deduplicate()`) for the residual fan-out.
- Downgrade the affected mart PK uniqueness test to `severity: warn` with a
  `TODO(#3915)` so it returns to error when source cleanup completes.
- `base_powerschool__student_enrollments` date-range joins currently need no
  tiebreaker.

**`_dagster_partition_key` in SchoolMint Grow staging** is the Grow `archived`
flag (`'f'` = not archived, `'t'` = archived). Most Grow staging models filter
to `'f'`; `stg_schoolmint_grow__rubrics__measurement_groups__measurements` and
`stg_schoolmint_grow__measurements` intentionally do not, so observation FKs to
archived rubrics/measurements still resolve. Don't re-add the filter to those
two models without understanding the FK-coverage tradeoff.

**`stg_google_sheets__people__locations` column naming**: `location_region`
holds long-form entity names (`TEAM Academy Charter School`,
`KIPP Cooper Norcross Academy`, `KIPP Miami`, `KIPP Paterson`); `city` holds the
short canonical names (`Newark` / `Camden` / `Miami` / `Paterson`). For region
lookups by short name, use `city`. For mapping `_dbt_source_project` to region,
use `dim_regions.dagster_code_location`.

**`dim_staff` is all-time staff (~4,600), not active-only.** For an active-staff
grain, spine on `dim_staff_work_assignments` where `is_current` (which already
excludes terminated staff via termination date). Do NOT filter
`dim_work_assignment_status.status_name != 'Terminated'` to get "active" — that
assignment-status field is misaligned with the roster's `worker_status_code` and
over-drops (~100 roster-active staff). The roster active+primary set (~1,526)
runs ~30 larger than the marts' current-primary set (hire/term timing). `entity`
(KTAF vs Region) derives from `business_unit_name`
(`KIPP TEAM and Family Schools Inc.` = KTAF, else Region).

**`stg_renlearn__star` is the consolidated STAR model** — the Nov-2025
"consolidate star calcs" refactor disabled `int_renlearn__star_rollup`
(`config: enabled: false`; leave it) and folded the derived columns
(`academic_year`, `star_subject`/`star_discipline`, `administration_window`
Fall/Winter/Spring→BOY/MOY/EOY, benchmark int-flags, `rn_subject_*`) into this
kipptaf-level `union_relations` view (materialized table). All STAR consumers
read it. Edit/consume STAR here, not the rollup.

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

## kipptaf-Specific Variables

`bigquery_external_connection_name`:
`projects/teamster-332318/locations/us/connections/biglake-teamster-gcs`

dbt Cloud project ID: `211862`.

## dbt Cloud CI

CI job: `dbt build --select state:modified+ --full-refresh`, target `staging`,
defers to Staging environment.

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
