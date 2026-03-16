# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Factory for outbound data extract assets that query BigQuery and deliver files
to SFTP destinations. Used by the `extracts` module in code locations.

## Factory Function: `build_bigquery_query_sftp_asset()`

Produces a Dagster asset that:

1. Runs a BigQuery query (from inline SQL, a `.sql` file, or a schema dict)
2. Serializes the results to CSV, TSV, JSON, or gzipped JSON
3. Uploads the file to an SFTP destination via the `ssh_<destination_name>`
   resource

Asset key pattern: `[code_location, "extracts", destination_name, asset_name]`

Required resources at runtime:

- `gcs` — GCS resource
- `db_bigquery` — BigQuery client
- `ssh_<destination_name>` — SSH resource for the target SFTP server

## Parameters

| Parameter              | Purpose                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| `query_config`         | `{"type": "text"\|"file"\|"schema", "value": ...}`                   |
| `file_config`          | `{"stem": ..., "suffix": "csv"\|"json"\|"json.gz"\|"tsv", ...}`      |
| `destination_config`   | `{"name": "<ssh_key_suffix>", "path": "<remote_dir>"}`               |
| `partitions_def`       | Optional `PartitionsDefinition`; asset is unpartitioned by default   |
| `automation_condition` | Optional override; defaults to `None` (no condition)                 |
| `deps`                 | Optional explicit dep list; overrides the default table-name dep key |

File stems support `{today}` and `{now}` substitutions (and partition dimension
names for partitioned assets).

## Overriding deps and automation_condition

By default the asset's only Dagster dep is inferred from `query_config` — the
BigQuery table name becomes `AssetKey([code_location, "extracts", table_name])`.

Pass explicit `deps` to wire in additional upstream assets (e.g., a staging
table that is the true data source) or to bypass intermediate VIEW assets that
would otherwise fan out cross-partition updates. Pass `automation_condition` to
enable reactive triggering (typically `AutomationCondition.eager()`).

Example — `intacct_extract` deps rationale:

- `stg_adp_payroll__general_ledger_file` (TABLE, partitioned) — partition-aware;
  updates one partition at a time
- `rpt_gsheets__intacct_integration_file` (VIEW, same partitions) — partition-
  aware; triggers when the VIEW model code changes
- `stg_google_sheets__finance__payroll_code_mapping` (TABLE, non-partitioned) —
  fans out to ALL extract partitions when the mapping table refreshes
