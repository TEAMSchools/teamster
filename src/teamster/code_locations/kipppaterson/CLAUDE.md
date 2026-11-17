# CLAUDE.md — `teamster/code_locations/kipppaterson/`

## Identity

```python
CODE_LOCATION = "kipppaterson"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

## Active Integrations

| Module                  | Type                         | Trigger                                                               |
| ----------------------- | ---------------------------- | --------------------------------------------------------------------- |
| `dbt`                   | dbt assets                   | `AutomationConditionSensor`                                           |
| `powerschool` (sis/dlt) | dlt assets (Oracle→BigQuery) | sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh) |
| `amplify` (mclass sftp) | SFTP assets                  | sensor (`build_amplify_mclass_sftp_sensor`)                           |
| `cambium`               | SFTP assets                  | sensor (`couchdrop_sftp_sensor`)                                      |
| `deanslist`             | API assets                   | schedule (nightly)                                                    |
| `edplan`                | SFTP assets                  | sensor (`build_edplan_sftp_sensor`)                                   |
| `finalsite`             | API + SFTP assets            | schedule (`contacts`, 00:15 + 12:00 ET) + sensor (`status_report`)    |
| `pearson`               | SFTP assets                  | manual only (retired; Cambium replaced it)                            |
| `extracts`              | BigQuery→SFTP                | schedule (3am)                                                        |
| `titan`                 | SFTP assets                  | sensor (`build_titan_sftp_sensor`)                                    |
| `couchdrop`             | sensor only                  | sensor (Google Drive watcher: cambium, finalsite)                     |

## PowerSchool via dlt

dlt wiring and schedule: `libraries/dlt/CLAUDE.md` → `powerschool/`. Pool limit:
same file → _Pool limits_. Paterson's tunnel needs `enable_legacy_rsa=True` on
`ssh_powerschool`. Design:
`docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md`.

- PS Oracle + SSH creds via `dagster-cloud.yaml` (`PS_DB_*`, `PS_SSH_*`)
- Ingestion writes to BigQuery `dagster_kipppaterson_dlt_powerschool`; the dbt
  `powerschool` package `staging/dlt` variant is enabled here
- `couchdrop_sftp_sensor` carries no PowerSchool files; it watches Cambium
  `njsla` and Finalsite `status_report`

## Schedules

`stg_finalsite__contacts` carries the shared `CONTACTS_STAGING_FRESHNESS_POLICY`
from the finalsite library, as in every district. The
`AutomationConditionSensor` targets `AssetSelection.all()`, so it covers the
`dbt` assets plus EdPlan `njsmart_powerschool`, the one Paterson SFTP asset that
passes an `automation_condition` (`AutomationCondition.eager()`) — that asset
materializes from either its own sensor or the automation sensor.
