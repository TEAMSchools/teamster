# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Identity

```python
CODE_LOCATION = "kipptaf"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kipptaf`

## Active Integrations

| Module                   | Assets                                                    | Schedules                  | Sensors                 |
| ------------------------ | --------------------------------------------------------- | -------------------------- | ----------------------- |
| `dbt`                    | 3 asset groups (see below)                                | —                          | —                       |
| `dlt`                    | Illuminate (active), Salesforce (WIP), Zendesk (disabled) | daily + hourly             | —                       |
| `google`                 | Directory, Forms, AppSheet specs, Sheets specs            | directory, forms           | bigquery, forms, sheets |
| `adp`                    | payroll SFTP + WFN API (WFM disabled)                     | WFN schedule               | WFN + payroll sensors   |
| `airbyte`                | asset specs                                               | schedule                   | disabled                |
| `collegeboard`           | SFTP assets                                               | —                          | —                       |
| `coupa`                  | API assets                                                | schedule                   | —                       |
| `deanslist`              | API assets                                                | —                          | sensor                  |
| `extracts`               | BigQuery→SFTP                                             | schedule                   | —                       |
| `knowbe4`                | API assets                                                | schedule                   | —                       |
| `ldap`                   | LDAP assets                                               | schedule                   | disabled                |
| `level_data`             | Grow API assets                                           | schedule                   | —                       |
| `nsc`                    | SFTP assets                                               | —                          | —                       |
| `overgrad`               | API assets                                                | —                          | —                       |
| `performance_management` | SFTP assets                                               | —                          | —                       |
| `powerschool`            | enrollment API                                            | schedule                   | —                       |
| `smartrecruiters`        | report assets                                             | schedule                   | —                       |
| `surveys`                | op-based email job                                        | schedule (Mon/Wed/Fri 9am) | —                       |
| `tableau`                | workbook refresh assets                                   | schedule                   | —                       |
| `zendesk`                | assets                                                    | schedule                   | —                       |
| `couchdrop`              | sensor only                                               | —                          | sensor                  |

## dbt Asset Groups (`dbt/assets.py`)

Kipptaf splits dbt into **three separate asset groups** with different resource
requirements and selection criteria:

| Asset variable            | `select`              | `exclude`                              | Notes                                         |
| ------------------------- | --------------------- | -------------------------------------- | --------------------------------------------- |
| `core_dbt_assets`         | `fqn:*`               | `source:adp_payroll+ tag:google_sheet` | Main run, 2000m CPU                           |
| `google_sheet_dbt_assets` | `tag:google_sheet`    | —                                      | Separate to isolate brittle gsheet deps       |
| `adp_payroll_dbt_assets`  | `source:adp_payroll+` | —                                      | Partitioned by payroll file; cannot be merged |

`all_dbt_assets` is a flat list of all three groups, used only in `asset_specs`
for resolving exposure dep keys via `dagster_dbt_translator.get_asset_key`.

`core_dbt_assets` is the one used by `TableauServerResource` dependencies
(imported as `core_dbt_assets` from `kipptaf.dbt.assets`).

`asset_specs` also includes dbt **exposure** asset specs (non-Tableau exposures
only) built from the manifest.

## `google` Sub-module

Aggregates all Google Workspace integrations into a single importable module:

- `appsheet` / `sheets` — produce `AssetSpec`s (external, sensor-driven)
- `directory` — user/group provisioning ops + assets
- `forms` — Google Forms response assets; sensor lists forms from Drive and
  triggers runs
- `bigquery` — sensor that watches BigQuery job completions

## Tableau Workbook Scheduling

`tableau/schedules.py` dynamically builds `extract_refresh_schedules` from
`workbook_refresh_assets`: a `ScheduleDefinition` is created for each workbook
asset whose metadata contains a `cron_schedule` key. The criterion is **"does
Dagster own this workbook's refresh trigger?"** — if yes, set `cron_schedule` in
the exposure's `asset.metadata`; if the workbook is refreshed by another system
(e.g. Tableau Server's built-in schedule), omit it.

See `src/dbt/kipptaf/CLAUDE.md` for the full exposure YAML reference.

## `surveys` Module

Pure op-based pipeline (no assets): queries BigQuery for pending survey
respondents → sends batched BCC emails via SMTP. Runs Mon/Wed/Fri at 9am.

## `resources.py`

Location-specific resource instances (not shared with other code locations): ADP
WFN, Airbyte Cloud workspace, Coupa, Outlook SMTP, Google Directory, KnowBe4,
LDAP, PowerSchool Enrollment, LevelData Grow, SmartRecruiters, Tableau Server,
and several SSH resources.

## Asset Checks

`asset_checks.py` defines freshness checks on ADP WFN people models (deadline
1:15am, 45-minute window).

## Disabled Integrations

`adp` WFM is not integrated (no schedules or assets). Reusable library code for
`alchemer`, `dayforce`, `fivetran`, and `adp/workforce_manager` is preserved
under `src/teamster/libraries/` for future use.
