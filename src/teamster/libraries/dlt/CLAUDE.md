# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

DLT (data load tool) pipeline assets for source systems that use the
`dagster-dlt` integration. Each sub-library wraps a DLT source + custom
`DagsterDltTranslator` to control asset keys.

## Sub-libraries

### `illuminate/`

Loads tables from the **Illuminate** (assessment platform) PostgreSQL database
directly to BigQuery using `dlt`'s `sql_database` source with PyArrow backend.

- Asset keys: `[code_location, "dlt", "illuminate", schema, table]`
- `filter_date_taken_callback` handles a PostgreSQL `infinity` date value in
  certain tables that breaks psycopg
- Factory:
  `build_illuminate_dlt_assets(sql_database_credentials, code_location, schema, table_name)`

### `salesforce/`

Loads Salesforce objects to BigQuery. Pipeline and helpers are adapted from the
`dlt` Salesforce source. Currently commented out / inactive in `kipptaf`.

### `zendesk/`

Loads Zendesk Support data (tickets, users, organizations, etc.) to BigQuery
using a vendored DLT Zendesk pipeline.

- Asset keys: `[code_location, "dlt", "zendesk", "support", resource_name]`
- Factory:
  `build_zendesk_support_dlt_assets(zendesk_credentials, code_location)`
- Vendored pipeline in `zendesk/pipeline/` handles auth via
  `TZendeskCredentials` and API pagination

## Notes

All DLT assets use `DagsterDltResource` (from `dagster-dlt`) and write directly
to BigQuery — they do not go through the GCS IO managers.
