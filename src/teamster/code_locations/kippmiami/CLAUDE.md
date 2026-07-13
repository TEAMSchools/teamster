# CLAUDE.md — `teamster/code_locations/kippmiami/`

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
| `dlt/focus`   | dlt assets    | schedule (daily 04:00 ET)                 |

## Florida-Specific

Miami is the only code location with `fldoe` (Florida Department of Education
assessment data — FSA, EOC, Science). These are SFTP assets from a Florida state
data file drop.

## PowerSchool Configuration

Uses **ODBC** (live Oracle tunnel). Config YAMLs under `powerschool/config/` —
same structure as other NJ schools.
