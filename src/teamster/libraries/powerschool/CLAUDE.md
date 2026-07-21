# CLAUDE.md — `teamster/libraries/powerschool/`

> **`sis/odbc/` is ARCHIVED (retired 2026-07; no importers).** All districts
> migrated PowerSchool SIS ingestion to dlt (`libraries/dlt/powerschool/`) or,
> for Miami, to Focus. The odbc code and this section are kept for reference
> only. `sis/sftp/` and `enrollment/` are unaffected.

Two separate PowerSchool integrations with different protocols:

- `sis/odbc/` — Oracle ODBC queries via SSH tunnel (ARCHIVED; was primary SIS
  data)
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

**Per-table cursor + key (not uniform).** The incremental cursor and merge key
vary by table: `students`/`storedgrades` use `transaction_date` (no
`whenmodified` column); `assignmentscore` uses `whenmodified` and keys on
`assignmentscoreid` (no `dcid`). Source of truth:
`code_locations/kippnewark/powerschool/assets.py` + `config/*.yaml`. Verify real
Oracle column names/case without a tunnel by querying the landed
`kippnewark_powerschool.src_powerschool__*` external tables via the BigQuery
MCP.

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

## Timeouts

`call_timeout` on `PowerSchoolODBCResource` governs a **single Oracle
round-trip**, not total query wall time. Sizing it as query time oversizes it —
healthy COUNT probes complete in <500ms. Default is 60s.

Sensor-tick budget: Dagster sensor ticks hard-cap at 600s. Keep
`call_timeout × max_attempts` well below 600s so a hung round-trip raises
`DPI-1067` (with the in-flight SQL) before Dagster kills the tick with an opaque
`DagsterUserCodeUnreachableError`.

## Logging quirks

The `dagster - INFO - resource:db_powerschool - Executing query:` log line is
truncated to its prefix in GCP `textPayload` — the multi-line SQL on the
following lines is dropped. After a `DPY-4024` fires the pod stops emitting logs
immediately, so the in-flight SQL is not recoverable post-hoc. Add a pre-query
`log.info(f"COUNT {table}")` in `_fetch_count()` if you need to attribute future
timeouts to a specific table.

## Sensor vs. schedule staleness checks

Sensors call `evaluate_asset_staleness()` (per-asset COUNT probes against
Oracle, with retry). Schedules call `enumerate_partitions_for_schedule()` (no DB
access — every asset × every partition in the limited window). Schedules run
once daily and the partition window is already constrained; COUNT probes added
no signal and were a recurring `DPY-4024` source on `assignmentscore` /
`pgfinalgrades`. Do not reintroduce DB calls into the schedule path.

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
