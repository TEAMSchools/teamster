# CLAUDE.md — `teamster/code_locations/kipppaterson/`

## Identity

```python
CODE_LOCATION = "kipppaterson"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kipppaterson`

## Active Integrations

| Module                  | Type                         | Trigger                                                               |
| ----------------------- | ---------------------------- | --------------------------------------------------------------------- |
| `dbt`                   | dbt assets                   | `AutomationConditionSensor`                                           |
| `powerschool` (sis/dlt) | dlt assets (Oracle→BigQuery) | sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh) |
| `amplify` (mclass sftp) | SFTP assets                  | sensor (`build_amplify_mclass_sftp_sensor`)                           |
| `deanslist`             | API assets                   | schedule (nightly)                                                    |
| `finalsite`             | API + SFTP assets            | schedule (`contacts`, 4am) + sensor (`status_report`)                 |
| `pearson`               | SFTP assets                  | `AutomationConditionSensor`                                           |
| `extracts`              | BigQuery→SFTP                | schedule (3am)                                                        |
| `couchdrop`             | sensor only                  | sensor (Google Drive watcher, Finalsite only)                         |

## PowerSchool via dlt

Paterson ingests PowerSchool with **dlt**, syncing directly from its Oracle
database through an in-process paramiko SSH tunnel (`ssh_powerschool` resource,
`enable_legacy_rsa=True`) and landing to BigQuery via keyless ADC (issue #3807).
This is the pilot/template for migrating the ODBC districts (`kippnewark`,
`kippcamden`, `kippmiami`) off `sshpass`. ONE `@dlt_assets` multi-asset covers
all 48 tables (`powerschool/sis/dlt/`); `cursor_column: null` tables always
replace. Config in `powerschool/sis/dlt/config/assets.yaml` (per-table
`cursor_column` + `intraday`/`nightly` membership booleans). Intraday selection
is decided by `kipppaterson__powerschool__dlt__intraday_sensor` (probe +
dlt-state baseline); the nightly schedule full-refreshes its targets
unconditionally and re-baselines. Design:
`docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md`.

Consequences:

- `dlt` (`DagsterDltResource`) wired in `definitions.py`; `ssh_powerschool`
  (`SSHResource`) built by the shared `get_powerschool_ssh_resource()` factory
  in `core/resources.py` and wired in `definitions.py`; PS Oracle + SSH creds
  via `dagster-cloud.yaml` (`PS_DB_*`, `PS_SSH_*`)
- Ingestion writes to BigQuery `dagster_kipppaterson_dlt_powerschool`; the dbt
  `powerschool` package `staging/dlt` variant is enabled here
- The former Couchdrop-SFTP PowerSchool feed is retired; `couchdrop_sftp_sensor`
  now watches Finalsite `status_report` only
- No `edplan`, `iready`, `overgrad`, `renlearn`, or `titan`
- The `dlt_powerschool_kipppaterson` pool stays at limit 1 (Dagster+ deployment
  settings, UI) so an overrunning tick serializes with the next instead of
  racing it
- **Go-live cutover**: the `powerschool` pipeline is new (the migration's
  per-table pipelines were `powerschool_<table>`), and its all-`NULLABLE` schema
  cannot `replace`-load into the migration-era tables (their identity column is
  `REQUIRED`). Before the first sensor/nightly load run against a dataset that
  already holds migration-era tables, drop them so the pipeline recreates fresh:
  `DROP SCHEMA IF EXISTS` the `dagster_kipppaterson_dlt_powerschool` dataset
  `CASCADE`. The dataset name is not branch-isolated, so this applies to prod
  go-live, not just branch testing.

## Schedules

Paterson has no freshness checks. PowerSchool dlt runs on an intraday
change-detection sensor (`kipppaterson__powerschool__dlt__intraday_sensor`,
15-min probe) plus one nightly cron schedule (unconditional full-refresh +
re-baseline, matching kippnewark's cadence). DeansList, Finalsite `contacts`,
and the PowerSchool autocomm `extracts` job add nightly schedules; Finalsite
`status_report` (`couchdrop_sftp_sensor`), Amplify
(`build_amplify_mclass_sftp_sensor`), and PowerSchool intraday are
sensor-driven. `AutomationConditionSensor` handles any assets with an automation
condition defined (e.g. `pearson`).
