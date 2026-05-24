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

### `extracts/powerschool/` special case

`rpt_powerschool__autocomm_*` models define a shared export format but are
**not** extracted here — regional projects source from them, filter to their
data, and push to their own PowerSchool instance. Exposures live in regional
projects, not kipptaf.

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
Date-range joins on `entrydate` silently drop these rows.

**`enroll_status` is student-level, not per-stint.** Sourced from
`stg_powerschool__students` and copied identically to every row in
`int_powerschool__student_enrollment_union`. Don't expect different stints for
the same student to carry different values.

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
or `dbt clone --select <upstream>` against staging.

## Single-PR cross-project workflow

CI only builds kipptaf; district staging schemas aren't auto-populated. For a PR
touching both a district model and a kipptaf consumer:

1. Add `target=staging` branch to affected `sources-kipp*.yml` (routes to
   `zz_stg_<district>_<source>`).
2. From each affected district project, run broad clone (no `--select`):
   `uv --directory <worktree> run dbt clone --target staging --state target/prod`
   to seed `zz_stg_<district>_*` from prod.
3. Push; CI reads staged regional via the schema branch.

Alternative to the two-PR pattern in `src/dbt/CLAUDE.md`.

## Verifying a coalesce/override layer is vestigial

Compare the override source against the **raw upstream**, not the
already-coalesced output column. `coalesce(override, raw)` trivially matches
`override` when it fires; comparing resolved-to-override hides every real
override. Source the staging model that feeds the coalesce, not the intermediate
that applies it.

Concretely: compare `stg_x.raw_col` (the staging input feeding the coalesce)
against `int_x.override_col` (the override source), not `int_x.resolved_col`
(the post-coalesce output).

## Model Layer Distinctions

- **`rpt_`** — analyst-built reporting views for external tools. Live in
  `models/extracts/`.
- **`dim_*` / `fct_*`** — dimensional marts for semantic layer. Live in
  `models/marts/`. Actively being developed; see
  `src/dbt/kipptaf/models/marts/CLAUDE.md` for column-naming rubric, hash-change
  discipline, and strict-chain rules.
