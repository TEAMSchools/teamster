# CLAUDE.md — `dbt/kipptaf/`

The **network-wide analytics project** — aggregates all source-system packages
and four district projects into network-level marts, reporting, and extracts.
Most complex dbt project in the repo.

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

### Selecting from `dbt_utils.star()` models

`base_` models using `star()` resolve columns from BigQuery at run time, not
SQL. YAML properties drift silently. **Rule**: enumerate columns explicitly when
joining these models (see `INFORMATION_SCHEMA.COLUMNS` query in
`src/dbt/CLAUDE.md`).

`union_relations` views have a related issue (stale compiled SQL) but are
handled automatically by `dbt_union_relations_automation_condition()`.

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

**Contract scope for `extracts/`**: `contract: enforced: true` applies to ALL
models under `extracts/`, including `intermediate/` — not just `rpt_` models.
This means `SELECT *`, `GROUP BY ALL`, and bare `null` columns are not safe in
any model under this directory.

**Disabled illuminate repositories**: 365, 413, 428 — disabled in
`models/illuminate/dlt/staging/repositories/properties.yml`. Check before adding
`ref()` calls to `int_illuminate__repository_data`.

**Disabled integrations** (project-level `+enabled: false`): ACT, ADP Workforce
Manager, ADP Workforce Now Fivetran, Alchemer, Coupa Fivetran, Dayforce,
Facebook, Illuminate Fivetran, Instagram.

## Cross-Project Refs

Sources models from: `powerschool`, `deanslist`, `edplan`, `iready`, `overgrad`,
`pearson`, `renlearn`, `titan`, `amplify`, `finalsite`. District-specific
PowerSchool data via multiple `sources-kipp*.yml` files.

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

## Model Layer Distinctions

- **`rpt_`** — analyst-built reporting views for external tools. Live in
  `models/extracts/`.
- **`dim_*` / `fct_*`** — dimensional marts for semantic layer. Live in
  `models/marts/`. Actively being developed.
