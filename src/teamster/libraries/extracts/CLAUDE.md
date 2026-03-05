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

| Parameter            | Purpose                                                         |
| -------------------- | --------------------------------------------------------------- |
| `query_config`       | `{"type": "text"\|"file"\|"schema", "value": ...}`              |
| `file_config`        | `{"stem": ..., "suffix": "csv"\|"json"\|"json.gz"\|"tsv", ...}` |
| `destination_config` | `{"name": "<ssh_key_suffix>", "path": "<remote_dir>"}`          |

File stems support `{today}` and `{now}` substitutions (and partition dimension
names for partitioned assets).
