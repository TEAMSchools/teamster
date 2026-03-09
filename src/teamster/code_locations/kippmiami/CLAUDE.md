# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Identity

```python
CODE_LOCATION = "kippmiami"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippmiami`

## Active Integrations

| Module        | Type          | Trigger                                   |
| ------------- | ------------- | ----------------------------------------- |
| `dbt`         | dbt assets    | `AutomationConditionSensor`               |
| `powerschool` | ODBC assets   | sensor (`build_powerschool_asset_sensor`) |
| `deanslist`   | API assets    | schedule (nightly)                        |
| `finalsite`   | API assets    | `AutomationConditionSensor`               |
| `fldoe`       | SFTP assets   | `AutomationConditionSensor`               |
| `iready`      | SFTP assets   | sensor (`build_iready_sftp_sensor`)       |
| `renlearn`    | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)     |
| `extracts`    | BigQuery→SFTP | schedule                                  |
| `couchdrop`   | sensor only   | sensor (Google Drive watcher)             |

## Florida-Specific

Miami is the only code location with `fldoe` (Florida Department of Education
assessment data — FSA, EOC, Science). These are SFTP assets from a Florida state
data file drop.

## PowerSchool Configuration

Uses **ODBC** (live Oracle tunnel). Config YAMLs under `powerschool/config/` —
same structure as other NJ schools.

## No Asset Checks

Miami does not define freshness checks (`asset_checks.py` is absent).

## Resources

All resources come from `teamster.core.resources`. Notable resources:

- `db_powerschool` — Oracle ODBC
- `ssh_powerschool` — SSH tunnel for ODBC
- `ssh_iready`, `ssh_renlearn` — SFTP
- `ssh_couchdrop` — Couchdrop SFTP
- `google_drive` — used by Couchdrop sensor
