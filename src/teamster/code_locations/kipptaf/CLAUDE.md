# CLAUDE.md — `teamster/code_locations/kipptaf/`

## Identity

```python
CODE_LOCATION = "kipptaf"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kipptaf`

## Active Integrations

| Module                   | Assets                                                    | Schedules        | Sensors                 |
| ------------------------ | --------------------------------------------------------- | ---------------- | ----------------------- |
| `dbt`                    | 3 asset groups (see below)                                | —                | —                       |
| `dlt`                    | Illuminate (active), Salesforce (WIP), Zendesk (disabled) | daily + hourly   | —                       |
| `google`                 | Directory, Forms, AppSheet specs, Sheets specs            | directory, forms | bigquery, forms, sheets |
| `adp`                    | payroll SFTP + WFN API (WFM disabled)                     | WFN schedule     | WFN + payroll sensors   |
| `airbyte`                | asset specs                                               | schedule         | disabled                |
| `collegeboard`           | SFTP assets                                               | —                | —                       |
| `coupa`                  | API assets                                                | schedule         | —                       |
| `deanslist`              | API assets                                                | —                | sensor                  |
| `extracts`               | BigQuery→SFTP                                             | schedule         | —                       |
| `knowbe4`                | API assets                                                | schedule         | —                       |
| `ldap`                   | LDAP assets                                               | schedule         | disabled                |
| `level_data`             | Grow API assets                                           | schedule         | —                       |
| `nsc`                    | SFTP assets                                               | —                | —                       |
| `overgrad`               | API assets                                                | —                | —                       |
| `performance_management` | SFTP assets                                               | —                | —                       |
| `powerschool`            | enrollment API                                            | schedule         | —                       |
| `smartrecruiters`        | report assets                                             | schedule         | —                       |
| `tableau`                | workbook refresh assets                                   | schedule         | —                       |
| `zendesk`                | assets                                                    | schedule         | —                       |
| `couchdrop`              | sensor only                                               | —                | sensor                  |

**Coupa Dagster code is aliased `l`** — resource `lResource`, env vars `l_*`
(`l_SFTP_*`, `l_API_*`), asset group `l`, and `libraries/l/` + `kipptaf/l/`
modules that the `coupa` submodule wires from. Grep `l` as well as `coupa`. The
dbt side is cleanly named `coupa`.

## dbt Asset Groups (`dbt/assets.py`)

Kipptaf splits dbt into **three separate asset groups** with different resource
requirements and selection criteria:

| Asset variable            | `select`              | `exclude`                              | Notes                                         |
| ------------------------- | --------------------- | -------------------------------------- | --------------------------------------------- |
| `core_dbt_assets`         | — (all)               | `source:adp_payroll+ tag:google_sheet` | Main run                                      |
| `google_sheet_dbt_assets` | `tag:google_sheet`    | —                                      | Separate to isolate brittle gsheet deps       |
| `adp_payroll_dbt_assets`  | `source:adp_payroll+` | —                                      | Partitioned by payroll file; cannot be merged |

`core_dbt_assets` is the one used by `TableauServerResource` dependencies
(imported as `core_dbt_assets` from `kipptaf.dbt.assets`).

`asset_specs` also includes dbt **exposure** asset specs (non-Tableau exposures
only) built from the manifest.

## `google` Sub-module

`appsheet` and `sheets` produce `AssetSpec`s (external, sensor-driven) — not
standard asset definitions.

## Tableau Workbook Scheduling

`tableau/schedules.py` dynamically builds `extract_refresh_schedules` from
`workbook_refresh_assets`: a `ScheduleDefinition` is created for each workbook
asset whose metadata contains a `cron_schedule` key. The criterion is **"does
Dagster own this workbook's refresh trigger?"** — if yes, set `cron_schedule` in
the exposure's `asset.metadata`; if the workbook is refreshed by another system
(e.g. Tableau Server's built-in schedule), omit it.

See `src/dbt/kipptaf/CLAUDE.md` for the full exposure YAML reference.

## Freshness Policies

`freshness.py` attaches `FreshnessPolicy.cron` to ADP WFN people models
(deadline 1:15am, 45-minute window).

## ADP WFN `workers` asset

Pulls with `asOfDate=<partition_key>` — each partition reconstructs ADP's state
as of that date from ADP's _current_ data (full snapshot, ~4.5–4.7k workers).
The schedule re-materializes only a rolling ~45-partition window
(`partition_keys[-45:]`, roughly −1 month / +2 weeks via `end_offset=14`), so an
ADP hard-delete / merge / backdated edit to a record older than the window
doesn't propagate until you manually rematerialize the affected partition span.
Absence from a re-pulled partition therefore means the record is gone from ADP.

The asset pulls the **list** endpoint (`GET hr/v2/workers?asOfDate=`), which
OMITS a worker not yet effective as of that date (hire date after the partition
date). The `_test_get_worker` harness in
`tests/resources/test_resource_adp_workforce_now.py` uses the **single-worker**
GET (`/workers/{aoid}`), which returns the worker regardless — so a
single-worker probe does NOT predict which partitions a bulk re-pull will place
them in.

## Illuminate DLT Schedule Split

Illuminate DLT assets are split across two schedules in
`dlt/illuminate/schedules.py`:

- **Hourly** (`illuminate_dlt_hourly_asset_job_schedule`): high-frequency
  `dna_assessments` tables that change as teachers grade and students test (e.g.
  `agg_student_responses*`, `students_assessments`)
- **Daily** (`illuminate_dlt_daily_asset_job_schedule`): reference/lookup tables
  and `dna_repositories` (e.g. `performance_bands`, `reporting_groups`,
  `fields`, individual repository tables)

New DLT assets must be assigned to the appropriate schedule.

## Adding a secret env var to `dagster-cloud.yaml`

Env mappings duplicate across `server_k8s_config` and `run_k8s_config`, and each
splits into a credentials block (password/username) and a host/port block — 4
insertion points per secret. Missing `run_k8s_config` leaves run pods broken
while the code server boots clean.

## Disabled Integrations

`adp` WFM is not integrated (no schedules or assets). Reusable library code for
`alchemer`, `dayforce`, `fivetran`, and `adp/workforce_manager` is preserved
under `src/teamster/libraries/` for future use.
