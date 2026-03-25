# CLAUDE.md — `dbt/kipptaf/`

The **primary network-wide analytics project** for KIPP TEAM & Family (TAF).
This is the most complex dbt project — it aggregates data from all source-system
packages and all four school projects to produce network-level marts, reporting
models, and extracts for downstream tools (Tableau, PowerSchool, Deanslist,
Google Sheets, etc.).

## Model Structure

```text
models/
  <source>/          # one folder per integration (adp, deanslist, powerschool, etc.)
    staging/         # materialized: table, contract: enforced: true
    intermediate/
  assessments/       # cross-source assessment aggregations
  people/            # staff/HR unified layer
  students/          # cross-school student data
  marts/             # dim_* and fct_* models for Tableau (contract: enforced: true)
  reporting/         # topline reporting
  extracts/          # outbound feeds
    tableau/         # Tableau-specific extract models
    deanslist/
    powerschool/
    google/
    ...
  exposures/         # dbt exposures (Tableau, etc.)
```

## Source File Conventions

Each integration with external table sources uses two source files:

- **`sources-external.yml`** — BigQuery external tables (GCS Avro or Google
  Sheets). Uses a dev-prefixed schema expression so dev/staging environments
  point to isolated schemas.
- **`sources-bigquery.yml`** — Native BQ tables. Uses a plain
  `"{{ project_name }}_<integration>"` schema (no dev prefix), always pointing
  to production. Used for frozen archive tables whose staging models have been
  disabled.

Both files use the same `name:` under `sources:` — dbt merges the table lists at
parse time.

**Archive table pattern**: When a staging or intermediate model is retired but
its data must be preserved, disable the model (`config: enabled: false` in its
properties YAML), add a BQ-native entry in `sources-bigquery.yml` pointing to
the schema where the model was materialized, and update downstream `ref()` calls
to `source()`. See `google/sheets/sources-bigquery.yml` and
`performance_management/sources-bigquery.yml` for examples.

**Shared-spreadsheet risk**: Google Sheets sources that share a spreadsheet URI
all trigger together when Dagster detects any tab change. Archive tabs on shared
sheets must be decoupled by converting to BQ-native sources (see above).

## Key Architectural Notes

**Cross-project refs**: This project references all source-system packages
(`powerschool`, `deanslist`, `edplan`, `iready`, `overgrad`, `pearson`,
`renlearn`, `titan`, `amplify`, `finalsite`, `overgrad`) and resolves models
from those packages at run time. School-specific PowerSchool data is sourced
from multiple `sources-kipp*.yml` files.

**Marts layer** (`models/marts/`): Dimensional models (`dim_*`, `fct_*`) used by
Tableau and the **Cube** semantic layer. All have `contract: enforced: true`.
Key models:

- `dim_students`, `dim_staff`, `dim_locations`, `dim_terms`, `dim_dates`,
  `dim_seats`
- `fct_attendance`, `fct_staff_attrition`, `fct_staff_terminations`,
  `fct_additional_earnings`, `fct_microgoals`

**People layer** (`models/people/`): Unified staff/HR view combining ADP, LDAP,
PowerSchool, and performance management data. Includes snapshots
(`snapshot_people__*`).

**Extracts layer** (`models/extracts/`): Outbound data feeds. Subdirectories map
to destination systems. All models have `contract: enforced: true`.

**`extracts/powerschool/`** is a special case: `rpt_powerschool__autocomm_*`
models define a consistent export file format shared across all regions. They
are **not** extracted here — regional dbt projects (`kippnewark`, `kippcamden`,
`kippmiami`) each source from these models and filter to their own data, then
push to their respective PowerSchool instance. Therefore `extracts/powerschool/`
has no dbt exposure in kipptaf; exposures live in the regional projects.

**Disabled integrations**: The following are fully disabled at the project level
via `+enabled: false` in `dbt_project.yml`: ACT, ADP Workforce Manager, ADP
Workforce Now Fivetran, Alchemer, Coupa Fivetran, Dayforce, Facebook, Illuminate
Fivetran, Instagram.

## Key Variables

| Variable                            | Value                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `current_academic_year`             | `2025`                                                                   |
| `current_fiscal_year`               | `2026`                                                                   |
| `local_timezone`                    | `America/New_York`                                                       |
| `cloud_storage_uri_base`            | `gs://teamster-kipptaf/dagster/kipptaf`                                  |
| `bigquery_external_connection_name` | `projects/teamster-332318/locations/us/connections/biglake-teamster-gcs` |

## dbt Cloud

This project is connected to dbt Cloud project ID `211862`. The `dbt-cloud`
block in `dbt_project.yml` enables dbt Cloud CI/CD.

### CI Chain

- PR opened → **Build Modified - CI** (defers to Staging, writes to
  `dbt_cloud_pr_*`)
- PR merged → **Parse - Staging** → triggers **Build Modified - Staging**
  (defers to Production)
- PR merged → **Parse - Production** (generates prod manifest)

The "Target name" field in dbt Cloud job settings controls `target.name` in
Jinja. Setting it to `"default"` means `target.name == 'default'` literally — it
is not a placeholder.

## Exposures

Every external tool that consumes kipptaf data **must have a dbt exposure**
defined in `models/exposures/`. Exposures make the dependency graph explicit and
power Dagster asset lineage.

**All exposures** require:

```yaml
exposures:
  - name: exposure_name_snake_case
    label: Human Readable Title
    type: dashboard | application | analysis | notebook | ml
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_tableau__some_model")
      - ref("rpt_gsheets__another_model")
    url: https://... # link to the external tool/workbook/sheet
    config:
      meta:
        dagster:
          kinds:
            - tableau # or: googlesheets, powerschool, etc.
```

**Tableau workbooks** may include the workbook LSID (`id`) under
`asset.metadata` to link the exposure to a specific Tableau Server workbook. Add
`cron_schedule` only when Dagster owns the refresh trigger:

```yaml
config:
  meta:
    dagster:
      kinds:
        - tableau
      asset:
        metadata:
          id: <tableau-workbook-lsid-uuid> # always include if known
          cron_schedule: "0 7 * * *" # only if Dagster manages the refresh
```

- `id` only → workbook is tracked in the asset graph but refreshed externally
- `id` + `cron_schedule` → Dagster owns the refresh schedule
- neither → workbook exposure with no asset-level metadata

Tableau workbooks with no metadata at all can omit the `asset` block entirely —
just the `kinds: [tableau]` is sufficient.

Exposure files live in `models/exposures/` grouped by tool: `tableau.yml`,
`google-sheets.yml`, `google-appsheet.yml`, etc.

## Model Conventions

See `src/dbt/CLAUDE.md` for shared per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns, documentation standards) that apply to all
dbt projects. The following are **kipptaf-specific** additions.

### `dbt_project.yml` — inherited defaults

These settings are applied at the directory level and **must not be repeated
per-model** unless overriding. When reviewing model YAML files, do not flag the
absence of these settings — they are intentionally inherited.

| Directory / pattern                    | `materialized` | `contract: enforced`        |
| -------------------------------------- | -------------- | --------------------------- |
| All integration `staging/`             | `table`        | `true`                      |
| `extracts/`                            | (view default) | `true`                      |
| `marts/`                               | (view default) | `true`                      |
| `illuminate/dlt/staging/repositories/` | `table`        | `false` (explicit override) |

**Disabled illuminate repository models**: Repositories 365, 413, and 428 are
disabled in `models/illuminate/dlt/staging/repositories/properties.yml`. Check
this file before adding new `ref()` calls to `int_illuminate__repository_data`.

**Schema overrides**: `extracts/tableau/` sets `+schema: tableau`, so
`rpt_tableau__*` models land in `kipptaf_tableau`, not `kipptaf_extracts`.
`extracts/` itself uses `+schema: extracts`.

**`reporting/`** (`+schema: reporting`) has no contract or materialization
defaults set — it is a separate layer from `extracts/` and is not where `rpt_`
models live.

### Model layer distinctions

**`rpt_` models** are analyst-built reporting views that serve as the data
source for external reporting tools (Tableau, Google Sheets, PowerSchool, etc.).
They live in `models/extracts/` and are distinct from the data mart layer.

**`dim_*` / `fct_*` models** are dimensional data mart models being built for
use with a semantic layer. They live in `models/marts/`. This layer is actively
being developed.

### Selecting from models that use `dbt_utils.star()`

Several `base_` models (e.g. `base_kippadb__contact`, `base_powerschool__*`)
generate their columns via `dbt_utils.star()`, which reads the BigQuery relation
schema at dbt run time — not from the SQL source. This means:

- The model's actual columns are only knowable from BigQuery, not from the SQL
  file
- YAML property files for these models drift silently unless actively maintained
- Selecting `c.*` from them in downstream models makes the downstream column
  list invisible — you won't notice when columns are added, renamed, or removed

**Rule**: When joining a `dbt_utils.star()` model, enumerate columns explicitly.
Get the authoritative list from `INFORMATION_SCHEMA.COLUMNS`:

```sql
select column_name
from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
where table_name = '<model_name>'
order by ordinal_position
```

Then list them in your `SELECT` and update the YAML properties to match.

**Note on `union_relations` views**: Views using the `union_relations` macro
have a related but distinct problem — the macro compiles to an explicit column
list at dbt run time, so stale compiled SQL won't pick up new upstream columns
until re-materialized. This is handled automatically by
`dbt_union_relations_automation_condition()` (see PR
[#3440](https://github.com/TEAMSchools/teamster/pull/3440)). The guidance above
applies to non-`union_relations` models where you are joining a star-generated
base model directly.
