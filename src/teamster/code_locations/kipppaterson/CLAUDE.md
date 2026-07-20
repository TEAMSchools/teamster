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
`kippcamden`, `kippmiami`) off `sshpass`. ONE probe-gated `@dlt_assets`
multi-asset covers all 48 tables (`powerschool/sis/dlt/`): the op probes each
selected table's `COUNT(*)`/`MAX(cursor_column)` and full-replaces only on
signature drift (signature in dlt resource state, restored from BigQuery);
`cursor_column: null` tables always replace. Config in
`powerschool/sis/dlt/config/assets.yaml`; two schedules in `schedules.py` subset
the multi-asset (intraday 15-min = 23 cursor tables; nightly = 25). Design:
`docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md`.

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
  `REQUIRED`). Before the first op-gate run against a dataset that already holds
  migration-era tables, drop them so the pipeline recreates fresh:
  `DROP SCHEMA IF EXISTS` the `dagster_kipppaterson_dlt_powerschool` dataset
  `CASCADE`. The dataset name is not branch-isolated, so this applies to prod
  go-live, not just branch testing.

## Schedules

Paterson has no freshness checks. PowerSchool dlt runs on two cron schedules
(intraday 15-min + nightly gradebook, matching kippnewark's cadence). DeansList,
Finalsite `contacts`, and the PowerSchool autocomm `extracts` job add nightly
schedules; Finalsite `status_report` (`couchdrop_sftp_sensor`) and Amplify
(`build_amplify_mclass_sftp_sensor`) are sensor-driven.
`AutomationConditionSensor` handles any assets with an automation condition
defined (e.g. `pearson`).
