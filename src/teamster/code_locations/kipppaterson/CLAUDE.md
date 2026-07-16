# CLAUDE.md — `teamster/code_locations/kipppaterson/`

## Identity

```python
CODE_LOCATION = "kipppaterson"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")
```

GCS bucket: `teamster-kipppaterson`

## Active Integrations

| Module                  | Type                         | Trigger                                               |
| ----------------------- | ---------------------------- | ----------------------------------------------------- |
| `dbt`                   | dbt assets                   | `AutomationConditionSensor`                           |
| `powerschool` (sis/dlt) | dlt assets (Oracle→BigQuery) | schedule (intraday 15-min + nightly gradebook)        |
| `amplify` (mclass sftp) | SFTP assets                  | sensor (`build_amplify_mclass_sftp_sensor`)           |
| `deanslist`             | API assets                   | schedule (nightly)                                    |
| `finalsite`             | API + SFTP assets            | schedule (`contacts`, 4am) + sensor (`status_report`) |
| `pearson`               | SFTP assets                  | `AutomationConditionSensor`                           |
| `extracts`              | BigQuery→SFTP                | schedule (3am)                                        |
| `couchdrop`             | sensor only                  | sensor (Google Drive watcher, Finalsite only)         |

## PowerSchool via dlt

Paterson ingests PowerSchool with **dlt**, syncing directly from its Oracle
database through an in-process paramiko SSH tunnel (`ssh_powerschool` resource,
`enable_legacy_rsa=True`) and landing to BigQuery via keyless ADC (issue #3807).
This is the pilot/template for migrating the ODBC districts (`kippnewark`,
`kippcamden`, `kippmiami`) off `sshpass`. Assets are defined in
`powerschool/sis/dlt/` (per-table `@dlt_assets`, full-refresh `replace`); config
in `powerschool/sis/dlt/config/assets.yaml`; two cron schedules in
`powerschool/sis/dlt/schedules.py`.

Consequences:

- `dlt` (`DagsterDltResource`) + `ssh_powerschool` (`SSHResource`) resources in
  `definitions.py`; PS Oracle + SSH creds wired via `dagster-cloud.yaml`
  (`PS_DB_*`, `PS_SSH_*`)
- Ingestion writes to BigQuery `dagster_kipppaterson_dlt_powerschool`; the dbt
  `powerschool` package `staging/dlt` variant is enabled here
- The former Couchdrop-SFTP PowerSchool feed is retired; `couchdrop_sftp_sensor`
  now watches Finalsite `status_report` only
- No `edplan`, `iready`, `overgrad`, `renlearn`, or `titan`
- **Go-live**: set a low concurrency limit on the `dlt_powerschool_kipppaterson`
  pool (Dagster+ deployment settings, UI) before the intraday schedule fans out,
  so the per-table pipelines don't overwhelm the shared dlt state table

## Schedules

Paterson has no freshness checks. PowerSchool dlt runs on two cron schedules
(intraday 15-min + nightly gradebook, matching kippnewark's cadence). DeansList,
Finalsite `contacts`, and the PowerSchool autocomm `extracts` job add nightly
schedules; Finalsite `status_report` (`couchdrop_sftp_sensor`) and Amplify
(`build_amplify_mclass_sftp_sensor`) are sensor-driven.
`AutomationConditionSensor` handles any assets with an automation condition
defined (e.g. `pearson`).
