# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Identity

```python
CODE_LOCATION = "kipppaterson"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kipppaterson`

## Active Integrations

| Module                   | Type                      | Trigger                                     |
| ------------------------ | ------------------------- | ------------------------------------------- |
| `dbt`                    | dbt assets                | `AutomationConditionSensor`                 |
| `powerschool` (sis/sftp) | SFTP assets via Couchdrop | `AutomationConditionSensor`                 |
| `amplify` (mclass sftp)  | SFTP assets               | sensor (`build_amplify_mclass_sftp_sensor`) |
| `finalsite`              | API assets                | `AutomationConditionSensor`                 |
| `pearson`                | SFTP assets               | `AutomationConditionSensor`                 |
| `couchdrop`              | sensor only               | sensor (Google Drive watcher)               |

## Critical Difference: PowerSchool via SFTP

Paterson is the **only** school location that does **not** use a live Oracle
ODBC connection for PowerSchool. Instead, PowerSchool data arrives as CSV file
drops on Couchdrop (Google Drive-backed SFTP). Assets are defined in
`powerschool/sis/sftp/` and use `ssh_resource_key="ssh_couchdrop"`.

Consequences:

- No `db_powerschool` or `ssh_powerschool` resources in `definitions.py`
- No `db_bigquery` resource (no BigQuery writes from this location)
- No `io_manager_gcs_file` resource (no file-based IO manager needed)
- No extracts module (no BigQuery to query)
- No `deanslist`, `edplan`, `iready`, `overgrad`, `renlearn`, or `titan`

## No Asset Checks, No Schedules

Paterson has no freshness checks and no data-pull schedules. All ingestion is
sensor-driven (Couchdrop file drop detection) or `AutomationConditionSensor`.

## Resources

Minimal resource set — only GCS, dbt, Couchdrop, and Amplify SFTP:

- `gcs`, `io_manager`, `io_manager_gcs_avro`, `dbt_cli`
- `ssh_couchdrop`, `ssh_amplify`
- `google_drive` — used by Couchdrop sensor
