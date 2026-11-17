# CLAUDE.md — `teamster/code_locations/kippcamden/`

## Identity

```python
CODE_LOCATION = "kippcamden"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

## Active Integrations

| Module        | Type              | Trigger                                                               |
| ------------- | ----------------- | --------------------------------------------------------------------- |
| `dbt`         | dbt assets        | `AutomationConditionSensor`                                           |
| `powerschool` | dlt assets        | sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh) |
| `cambium`     | SFTP assets       | `AutomationConditionSensor`                                           |
| `deanslist`   | API assets        | schedule (nightly)                                                    |
| `edplan`      | SFTP asset        | sensor (`build_edplan_sftp_sensor`)                                   |
| `finalsite`   | API + SFTP assets | schedule (`contacts`, 00:15 + 12:00 ET) + sensor (`status_report`)    |
| `overgrad`    | API assets        | schedule                                                              |
| `pearson`     | SFTP assets       | manual only (retired; Cambium replaced it)                            |
| `titan`       | SFTP assets       | sensor (`build_titan_sftp_sensor`)                                    |
| `extracts`    | BigQuery→SFTP     | schedule (nightly, 3am)                                               |
| `couchdrop`   | sensor only       | sensor (Google Drive watcher)                                         |

## PowerSchool Configuration

dlt wiring and schedule: `libraries/dlt/CLAUDE.md` → `powerschool/`. Pool limit:
same file → _Pool limits_.

## Extracts

`extracts/` queries BigQuery and pushes CSV/JSON files to PowerSchool SFTP via
`build_bigquery_query_sftp_asset()`. Config: `extracts/config/powerschool.yaml`.
