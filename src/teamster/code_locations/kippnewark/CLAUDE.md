# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Identity

```python
CODE_LOCATION = "kippnewark"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippnewark`

## Active Integrations

| Module                  | Type          | Trigger                                     |
| ----------------------- | ------------- | ------------------------------------------- |
| `dbt`                   | dbt assets    | `AutomationConditionSensor`                 |
| `powerschool`           | ODBC assets   | sensor (`build_powerschool_asset_sensor`)   |
| `amplify` (mclass sftp) | SFTP assets   | sensor (`build_amplify_mclass_sftp_sensor`) |
| `deanslist`             | API assets    | schedule (nightly)                          |
| `edplan`                | SFTP asset    | sensor (`build_edplan_sftp_sensor`)         |
| `finalsite`             | API assets    | `AutomationConditionSensor`                 |
| `iready`                | SFTP assets   | sensor (`build_iready_sftp_sensor`)         |
| `overgrad`              | API assets    | schedule                                    |
| `pearson`               | SFTP assets   | `AutomationConditionSensor`                 |
| `renlearn`              | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)       |
| `titan`                 | SFTP assets   | sensor (`build_titan_sftp_sensor`)          |
| `extracts`              | BigQuery→SFTP | schedule                                    |
| `couchdrop`             | sensor only   | sensor (Google Drive watcher)               |

Newark is the most complete school code location — it uses every available
integration.

## PowerSchool Configuration

Uses **ODBC** (live Oracle tunnel). Config YAMLs under `powerschool/config/`.

## Asset Checks

`asset_checks.py` defines freshness checks on Titan assets
(`kippnewark/titan/person_data`, `stg_titan__person_data`) — deadline 11:30pm,
30-minute window.

## Resources

All resources come from `teamster.core.resources`. Notable resources:

- `db_powerschool` — Oracle ODBC
- `ssh_powerschool` — SSH tunnel for ODBC
- `ssh_amplify`, `ssh_edplan`, `ssh_iready`, `ssh_renlearn`, `ssh_titan` — SFTP
- `ssh_couchdrop` — Couchdrop SFTP
- `google_drive` — used by Couchdrop sensor
- `overgrad` — Overgrad API
