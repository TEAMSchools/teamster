# CLAUDE.md — `teamster/code_locations/kippnewark/`

## Identity

```python
CODE_LOCATION = "kippnewark"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

## Active Integrations

| Module                  | Type          | Trigger                                                               |
| ----------------------- | ------------- | --------------------------------------------------------------------- |
| `dbt`                   | dbt assets    | `AutomationConditionSensor`                                           |
| `powerschool`           | dlt assets    | sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh) |
| `amplify` (mclass sftp) | SFTP assets   | sensor (`build_amplify_mclass_sftp_sensor`)                           |
| `cambium`               | SFTP assets   | `AutomationConditionSensor`                                           |
| `deanslist`             | API assets    | schedule (nightly)                                                    |
| `edplan`                | SFTP asset    | sensor (`build_edplan_sftp_sensor`)                                   |
| `finalsite`             | API + SFTP    | schedule (contacts 00:15 + 12:00 ET) + couchdrop sensor               |
| `iready`                | SFTP assets   | sensor (`build_iready_sftp_sensor`)                                   |
| `overgrad`              | API assets    | schedule                                                              |
| `pearson`               | SFTP assets   | manual only (retired; Cambium replaced it)                            |
| `titan`                 | SFTP assets   | sensor (`build_titan_sftp_sensor`)                                    |
| `extracts`              | BigQuery→SFTP | schedule                                                              |
| `couchdrop`             | sensor only   | sensor (Google Drive watcher)                                         |

## PowerSchool Configuration

dlt wiring and schedule: `libraries/dlt/CLAUDE.md` → `powerschool/`. Pool limit:
same file → _Pool limits_.
