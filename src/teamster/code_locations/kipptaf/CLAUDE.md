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

## dbt Asset Groups (`dbt/assets.py`)

Kipptaf splits dbt into **three separate asset groups** with different resource
requirements and selection criteria:

| Asset variable            | `select`              | `exclude`                              | Notes                                         |
| ------------------------- | --------------------- | -------------------------------------- | --------------------------------------------- |
| `core_dbt_assets`         | `fqn:*`               | `source:adp_payroll+ tag:google_sheet` | Main run                                      |
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

## Asset Checks

`asset_checks.py` defines freshness checks on ADP WFN people models (deadline
1:15am, 45-minute window).

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

## Disabled Integrations

`adp` WFM is not integrated (no schedules or assets). Reusable library code for
`alchemer`, `dayforce`, `fivetran`, and `adp/workforce_manager` is preserved
under `src/teamster/libraries/` for future use.
