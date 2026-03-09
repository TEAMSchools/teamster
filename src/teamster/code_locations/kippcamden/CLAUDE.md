# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Identity

```python
CODE_LOCATION = "kippcamden"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippcamden`

## Active Integrations

| Module        | Type          | Trigger                                   |
| ------------- | ------------- | ----------------------------------------- |
| `_dbt`        | dbt assets    | `AutomationConditionSensor`               |
| `powerschool` | ODBC assets   | sensor (`build_powerschool_asset_sensor`) |
| `deanslist`   | API assets    | schedule (nightly)                        |
| `edplan`      | SFTP asset    | sensor (`build_edplan_sftp_sensor`)       |
| `finalsite`   | API assets    | `AutomationConditionSensor`               |
| `overgrad`    | API assets    | schedule                                  |
| `pearson`     | SFTP assets   | `AutomationConditionSensor`               |
| `titan`       | SFTP assets   | sensor (`build_titan_sftp_sensor`)        |
| `extracts`    | BigQuery→SFTP | schedule (nightly, 3am)                   |
| `couchdrop`   | sensor only   | sensor (Google Drive watcher)             |

## PowerSchool Configuration

Uses **ODBC** (live Oracle tunnel). Config YAMLs under `powerschool/config/`:

- `assets-full.yaml` — fiscal-year partitioned tables
- `assets-gradebook-full.yaml` / `assets-gradebook-monthly.yaml` — gradebook
- `assets-nightly.yaml` — nightly-partitioned tables
- `assets-nonpartition.yaml` — unpartitioned tables
- `assets-transactiondate.yaml` — transaction-date partitioned tables

## Asset Checks

`asset_checks.py` defines freshness checks on Titan assets
(`kippcamden/titan/person_data`, `stg_titan__person_data`) — deadline 11:30pm,
30-minute window.

## Extracts

`extracts/` queries BigQuery and pushes CSV/JSON files to PowerSchool SFTP via
`build_bigquery_query_sftp_asset()`. Config: `extracts/config/powerschool.yaml`.
Schedule runs at 3am nightly.

## Resources

All resources come from `teamster.core.resources`. No location-specific
`resources.py`. Notable resources:

- `db_powerschool` — Oracle ODBC
- `ssh_powerschool` — SSH tunnel for ODBC
- `ssh_edplan`, `ssh_titan` — SFTP
- `ssh_couchdrop` — Couchdrop SFTP (for Couchdrop sensor)
- `google_drive` — used by Couchdrop sensor
