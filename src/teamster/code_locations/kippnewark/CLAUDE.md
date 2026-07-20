# CLAUDE.md — `teamster/code_locations/kippnewark/`

## Identity

```python
CODE_LOCATION = "kippnewark"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippnewark`

## Active Integrations

| Module                  | Type          | Trigger                                                               |
| ----------------------- | ------------- | --------------------------------------------------------------------- |
| `dbt`                   | dbt assets    | `AutomationConditionSensor`                                           |
| `powerschool`           | dlt assets    | sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh) |
| `amplify` (mclass sftp) | SFTP assets   | sensor (`build_amplify_mclass_sftp_sensor`)                           |
| `deanslist`             | API assets    | schedule (nightly)                                                    |
| `edplan`                | SFTP asset    | sensor (`build_edplan_sftp_sensor`)                                   |
| `finalsite`             | API + SFTP    | schedule (contacts 4am) + couchdrop sensor                            |
| `iready`                | SFTP assets   | sensor (`build_iready_sftp_sensor`)                                   |
| `overgrad`              | API assets    | schedule                                                              |
| `pearson`               | SFTP assets   | `AutomationConditionSensor`                                           |
| `renlearn`              | SFTP assets   | sensor (`build_renlearn_sftp_sensor`)                                 |
| `titan`                 | SFTP assets   | sensor (`build_titan_sftp_sensor`)                                    |
| `extracts`              | BigQuery→SFTP | schedule                                                              |
| `couchdrop`             | sensor only   | sensor (Google Drive watcher)                                         |

## PowerSchool Configuration

Uses **dlt** (sensor-gated intraday + unconditional nightly full-refresh, over
57 tables), not ODBC. Config at `powerschool/sis/dlt/config/assets.yaml`
(per-table `cursor_column` + `intraday`/`nightly` membership booleans). Intraday
selection is decided by `kippnewark__powerschool__dlt__intraday_sensor` (probe +
dlt-state baseline); the nightly schedule full-refreshes its targets
unconditionally and re-baselines. Resources `ssh_powerschool` (paramiko tunnel)
and `db_powerschool` (Oracle creds) are built by the shared `core/resources.py`
factories. Writes directly to BigQuery — no GCS IO manager.
