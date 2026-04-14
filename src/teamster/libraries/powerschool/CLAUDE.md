# CLAUDE.md — `teamster/libraries/powerschool/`

Two separate PowerSchool integrations with different protocols:

- `sis/odbc/` — Live Oracle ODBC queries via SSH tunnel (primary SIS data)
- `sis/sftp/` — SFTP file ingestion (schema only; used by Paterson)
- `enrollment/` — PowerSchool Enrollment REST API

## `sis/odbc/` — PowerSchool SIS via Oracle ODBC

**`resources.py`** (`PowerSchoolODBCResource`): Connects to the PowerSchool
Oracle database via `oracledb`. Requires an active SSH tunnel (opened separately
via `SSHResource.open_ssh_tunnel()`).

**`assets.py`** (`build_powerschool_table_asset()`): Factory producing one
Dagster asset per PowerSchool table. Executes a SQLAlchemy `SELECT` with
optional `partition_column` filtering and streams results via Avro block files
for large-table efficiency. Key parameters:

- `partitions_def` — optional time-window partitions (monthly, fiscal year,
  etc.)
- `partition_column` — column to filter by partition window
- `partition_size` / `prefetch_rows` / `array_size` — Oracle cursor tuning knobs

**`sensors.py`** (`build_powerschool_asset_sensor()`): Sensor that detects stale
partitioned assets by comparing the last materialized partition's
`updated_at`-equivalent column against current data, triggering backfill runs.

**Code location config YAMLs** (under
`code_locations/<district>/powerschool/config/`):

- `assets-full.yaml` — fiscal-year partitioned tables
- `assets-gradebook-full.yaml` / `assets-gradebook-monthly.yaml` — gradebook
- `assets-nightly.yaml` — nightly-partitioned tables
- `assets-nonpartition.yaml` — unpartitioned tables
- `assets-transactiondate.yaml` — transaction-date partitioned tables

**`schema.py`**: `ORACLE_AVRO_SCHEMA_TYPES` — maps Oracle column types to Avro
types for schema inference.

## Connection Retry

`with_powerschool_retry()` in `utils.py` wraps `powerschool_connection()` with a
retry loop. All callers (sensors, schedules, assets) use it instead of
`powerschool_connection()` directly. The context manager itself cannot retry
because `@contextmanager` only allows one `yield`.

## Type Annotations

- `oracledb` lacks type stubs — `cursor.description` elements are `FetchInfo` at
  runtime but typed as broad unions. Use `trunk-ignore-begin(pyright)` blocks
  for code that accesses `.lower()` or `.name` on description elements.

## `enrollment/`

**`resources.py`** (`PowerSchoolEnrollmentResource`): REST client for the
PowerSchool Enrollment/Registration API (separate from SIS; handles enrollment
form submissions).

**`assets.py`** (`build_ps_enrollment_submission_records_asset()`): Fetches
submission records for a given enrollment form (dynamic partition by form ID).
