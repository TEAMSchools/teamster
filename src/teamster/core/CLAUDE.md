# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Shared infrastructure used by every code location and library. Nothing here is
integration-specific — it is the foundation all other modules build on.

## Files

### `resources.py`

Shared resource instances and factory functions imported by every code
location's `definitions.py`. Two categories:

**Factories** (called with arguments per code location):

- `get_io_manager_gcs_pickle(code_location)` → `GCSIOManager` (pickle, default
  IO manager)
- `get_io_manager_gcs_avro(code_location)` → `GCSIOManager` (Avro, used by
  SFTP/API assets)
- `get_io_manager_gcs_file(code_location)` → `GCSIOManager` (raw file, used by
  paginated Deanslist)
- `get_dbt_cli_resource(dbt_project, test=False)` → `DbtCliResource`
- `get_powerschool_ssh_resource()` → `SSHResource` (reads from shared env vars)

All IO manager factories redirect to `teamster-test` bucket when
`DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT=1`.

**Singletons** (shared across all code locations):

- `BIGQUERY_RESOURCE`, `GCS_RESOURCE`, `DLT_RESOURCE`
- `DEANSLIST_RESOURCE`, `OVERGRAD_RESOURCE`, `ZENDESK_RESOURCE`
- `GOOGLE_DRIVE_RESOURCE`, `GOOGLE_FORMS_RESOURCE`, `GOOGLE_SHEETS_RESOURCE`
- `DB_POWERSCHOOL` — Oracle ODBC resource (shared env vars)
- `SSH_COUCHDROP`, `SSH_EDPLAN`, `SSH_IREADY`, `SSH_RENLEARN`, `SSH_TITAN`,
  `SSH_RESOURCE_AMPLIFY` — SFTP resources

### `io_managers/gcs.py` — `GCSIOManager`

Custom IO manager extending `dagster-gcp`'s `PickledObjectGCSIOManager`. The key
extension is Hive-style partitioned GCS paths:

- **Date/datetime partition keys** → decomposed into
  `_dagster_partition_fiscal_year=YYYY/_dagster_partition_date=YYYY-MM-DD/_dagster_partition_hour=HH/_dagster_partition_minute=MM/data`
- **Non-date partition keys** → `_dagster_partition_key=<value>/data`
- **Multi-partition keys** → concatenated Hive partitions, sorted by dimension
  name

The epoch timestamp (`1970-01-01`) is treated as a resync signal and replaced
with the current timestamp.

Three `object_type` modes: `"pickle"`, `"avro"` (writes Fastavro container
files), `"file"` (writes raw bytes from a local file path). The `test=True` flag
prefixes GCS paths with `test/` to isolate test runs.

### `asset_checks.py`

Two functions used by every SFTP/API asset factory:

- `build_check_spec_avro_schema_valid(asset_key)` → `AssetCheckSpec` (declare
  the check)
- `check_avro_schema_valid(asset_key, records, schema)` → `AssetCheckResult`
  (warn — not fail — if records contain fields not present in the Avro schema)

All asset factories that yield Avro output call both of these.

### `automation_conditions.py`

Two dbt-specific `AutomationCondition` builders:

- `dbt_view_automation_condition()` — for VIEW models: re-runs on
  `newly_missing`, `code_version_changed`, or `execution_failed`
- `dbt_table_automation_condition()` — for TABLE models: also triggers on
  upstream data changes, including through intermediate views via
  `_build_any_ancestor_updated()` (recursive `any_deps_match` up to 5 levels)

### `utils/classes.py`

- `FiscalYear(datetime, start_month)` — computes `.fiscal_year` (int), `.start`
  (date), `.end` (date). Used throughout for July-based fiscal year
  calculations.
- `FiscalYearPartitionsDefinition` — `TimeWindowPartitionsDefinition` subclass
  with `cron_schedule="0 0 {start_day} {start_month} *"`.
- `CustomJSONEncoder` — JSON encoder that handles `timedelta`, `Decimal`,
  `bytes`, `datetime`, and `date` types.

### `utils/functions.py`

- `file_to_records(file_path, ...)` / `csv_string_to_records(csv_string, ...)` —
  read CSV into `list[dict]`, slugifying column names by default (spaces/special
  chars → underscores). Empty strings become `None`. Adds `source_file_name`
  when reading from a file path.
- `regex_pattern_replace(pattern, replacements)` — replaces `(?P<name>...)`
  regex named groups with values from a dict. Core of SFTP partition key
  substitution.
- `parse_partition_key(partition_key)` / `get_partition_key_path(...)` —
  converts a partition key string to a Hive-style GCS path segment list.
- `chunk(obj, size)` — yields successive list slices.
