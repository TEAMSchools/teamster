# CLAUDE.md — `teamster/code_locations/kippcamden/`

## Identity

```python
CODE_LOCATION = "kippcamden"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kippcamden`

## Active Integrations

| Module        | Type              | Trigger                                                               |
| ------------- | ----------------- | --------------------------------------------------------------------- |
| `dbt`         | dbt assets        | `AutomationConditionSensor`                                           |
| `powerschool` | dlt assets        | sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh) |
| `deanslist`   | API assets        | schedule (nightly)                                                    |
| `edplan`      | SFTP asset        | sensor (`build_edplan_sftp_sensor`)                                   |
| `finalsite`   | API + SFTP assets | schedule (`contacts`, 4am) + sensor (`status_report`)                 |
| `overgrad`    | API assets        | schedule                                                              |
| `pearson`     | SFTP assets       | `AutomationConditionSensor`                                           |
| `titan`       | SFTP assets       | sensor (`build_titan_sftp_sensor`)                                    |
| `extracts`    | BigQuery→SFTP     | schedule (nightly, 3am)                                               |
| `couchdrop`   | sensor only       | sensor (Google Drive watcher)                                         |

## PowerSchool Configuration

Uses **dlt** (sensor-gated intraday + unconditional nightly full-refresh, over
57 tables), not ODBC. Config at `powerschool/sis/dlt/config/assets.yaml`
(per-table `cursor_column` + `intraday`/`nightly` membership booleans). Intraday
selection is decided by `kippcamden__powerschool__dlt__intraday_sensor` (probe +
dlt-state baseline); the nightly schedule full-refreshes its targets
unconditionally and re-baselines. Resources `ssh_powerschool` (paramiko tunnel)
and `db_powerschool` (Oracle creds) are built by the shared `core/resources.py`
factories. Writes directly to BigQuery — no GCS IO manager.

## Extracts

`extracts/` queries BigQuery and pushes CSV/JSON files to PowerSchool SFTP via
`build_bigquery_query_sftp_asset()`. Config: `extracts/config/powerschool.yaml`.
Schedule runs at 3am nightly.
