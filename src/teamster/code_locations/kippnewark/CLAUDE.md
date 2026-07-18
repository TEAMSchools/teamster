# CLAUDE.md — `teamster/code_locations/kippnewark/`

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
| `powerschool`           | dlt assets    | schedules (intraday 15-min + nightly 2am)   |
| `amplify` (mclass sftp) | SFTP assets   | sensor (`build_amplify_mclass_sftp_sensor`) |
| `deanslist`             | API assets    | schedule (nightly)                          |
| `edplan`                | SFTP asset    | sensor (`build_edplan_sftp_sensor`)         |
| `finalsite`             | API + SFTP    | schedule (contacts 4am) + couchdrop sensor  |
| `iready`                | SFTP assets   | sensor (`build_iready_sftp_sensor`)         |
| `overgrad`              | API assets    | schedule                                    |
| `pearson`               | SFTP assets   | `AutomationConditionSensor`                 |
| `renlearn`              | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)       |
| `titan`                 | SFTP assets   | sensor (`build_titan_sftp_sensor`)          |
| `extracts`              | BigQuery→SFTP | schedule                                    |
| `couchdrop`             | sensor only   | sensor (Google Drive watcher)               |

## PowerSchool Configuration

Uses **dlt** (probe-gated, full-replace ingestion over 57 tables), not ODBC.
Config at `powerschool/sis/dlt/config/assets.yaml` (per-table `cursor_column` +
`schedule_tier`). Resources `ssh_powerschool` (paramiko tunnel) and
`db_powerschool` (Oracle creds) are built by the shared `core/resources.py`
factories. Writes directly to BigQuery — no GCS IO manager.
