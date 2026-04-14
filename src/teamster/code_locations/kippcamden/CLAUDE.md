# CLAUDE.md — `teamster/code_locations/kippcamden/`

## Identity

```python
CODE_LOCATION = "kippcamden"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippcamden`

## Active Integrations

| Module        | Type          | Trigger                                   |
| ------------- | ------------- | ----------------------------------------- |
| `dbt`         | dbt assets    | `AutomationConditionSensor`               |
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

Uses **ODBC** (live Oracle tunnel).

## Extracts

`extracts/` queries BigQuery and pushes CSV/JSON files to PowerSchool SFTP via
`build_bigquery_query_sftp_asset()`. Config: `extracts/config/powerschool.yaml`.
Schedule runs at 3am nightly.
