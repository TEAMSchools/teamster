# PowerSchool ODBC Staleness Refactor — Design Spec

**Date:** 2026-03-20 **Issue:**
[#2342](https://github.com/TEAMSchools/teamster/issues/2342) **Status:**
Approved

## Problem

`schedules.py` (330 lines) and `sensors.py` (360 lines) in
`libraries/powerschool/sis/odbc/` share ~90% identical logic for detecting stale
PowerSchool assets via Oracle ODBC queries. Both reach 7 levels of nesting at
their deepest point. `assets.py` also duplicates the SSH tunnel/connection
lifecycle and partition date window calculation.

## Goals

- **DRY**: eliminate ~250 lines of duplicated staleness detection logic
- **Readability**: reduce nesting from 7 levels to ≤3

## Out of Scope

- Changes to the `resources.py` implementation
- Changes to the asset factory signature, metadata, or output format
- Integration tests against the live Oracle database

## Architecture

After the refactor, responsibilities are:

| File           | Responsibility                                                                                                                                                                    |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `utils.py`     | `powerschool_connection()` context manager; `format_oracle_timestamp()`; `get_partition_window()`; `get_query_text()` (existing); `StalenessResult`; `evaluate_asset_staleness()` |
| `schedules.py` | `@schedule` decorator; call `evaluate_asset_staleness()`; group results → `RunRequest` yields                                                                                     |
| `sensors.py`   | `@sensor` decorator; job setup; call `evaluate_asset_staleness()`; group results → `SensorResult`                                                                                 |
| `assets.py`    | Use `powerschool_connection()` and `get_partition_window()` in place of inline lifecycle/window code                                                                              |
| `resources.py` | Unchanged                                                                                                                                                                         |

## Components

### `powerschool_connection()` — context manager

```python
@contextmanager
def powerschool_connection(ssh_resource, db_resource, log):
    log.info(f"Opening SSH tunnel to {ssh_resource.remote_host}")
    ssh_tunnel = ssh_resource.open_ssh_tunnel()
    try:
        connection = db_resource.connect()
    except Exception:
        ssh_tunnel.kill()  # tunnel open, connection failed — kill here and exit
        raise
    try:
        yield connection
    except Exception:
        log.exception("PowerSchool ODBC error")
        raise
    finally:
        connection.close()
        ssh_tunnel.kill()
```

- Takes `ssh_resource`, `db_resource`, and `log` (caller passes `context.log`)
- Handles tunnel open, connection, exception logging, and cleanup in one place
- Replaces the duplicated `try/except/try/finally` pattern in all three files
- The two `kill()` calls are on mutually exclusive paths: if `connect()` fails,
  execution leaves via the outer `except` before the inner `try/finally` is
  entered — `finally` never runs in that path. If `connect()` succeeds, `kill()`
  runs only in `finally`.
- Connection failures (outer `except`) are not logged here — they propagate to
  the Dagster framework, which logs them at the run level. Only errors during
  query execution (inner `except`) are logged by the context manager.

In `assets.py`, the context manager is called as
`powerschool_connection(ssh_powerschool, db_powerschool, context.log)`, where
`ssh_powerschool: SSHResource` and `db_powerschool: PowerSchoolODBCResource` are
Dagster-injected resource parameters on the `_asset` function (already present
in the existing signature — no changes to `required_resource_keys`).

### `format_oracle_timestamp(timestamp: float, tz: ZoneInfo) -> str`

Converts a float timestamp to an Oracle-compatible ISO string (no timezone,
microsecond precision). Currently duplicated 4× across `schedules.py` and
`sensors.py`.

### `get_partition_window(partition_key: str, partitions_def) -> tuple[str, str]`

Computes `(start_value, end_value)` ISO strings for a partition window. The end
is always the last microsecond of the day before the next period boundary:

- `FiscalYearPartitionsDefinition` → window is
  `[partition_start, partition_start + 1 year - 1 day @ 23:59:59.999999]`
  Example: partition key `2024-07-01` →
  `start_value=2024-07-01T00:00:00.000000`,
  `end_value=2025-06-30T23:59:59.999999`
- `MonthlyPartitionsDefinition` → window is
  `[(partition_start + relativedelta(months=1)) - relativedelta(days=1) @ 23:59:59.999999]`.
  Partition keys are always the 1st of a month, so this always yields the last
  calendar day of the same month. Example: partition key `2024-07-01` →
  `start_value=2024-07-01T00:00:00.000000`,
  `end_value=2024-07-31T23:59:59.999999`
- Any other type → raises `TypeError` (only the two types above are used in
  production; an unknown type indicates a programming error)

Both values are ISO strings without timezone info (Oracle `TO_TIMESTAMP`
compatible), at microsecond precision. "1 year" and "1 month" are computed with
`dateutil.relativedelta` (`relativedelta(years=1)` and `relativedelta(months=1)`
respectively), which handles leap years and month-length variations correctly.

Currently duplicated across `schedules.py`, `sensors.py`, and `assets.py`.

### `StalenessResult`

```python
@dataclass
class StalenessResult:
    asset_key: AssetKey
    partitions_def_identifier: str | None  # None for non-partitioned assets
    partition_key: str | None              # None for non-partitioned assets
```

`evaluate_asset_staleness()` returns **only stale assets** — every entry in the
result list represents an asset/partition that needs to be re-materialized.
Absence from the list means not stale.

`partition_key` is `None` for non-partitioned assets.
`partitions_def_identifier` is `None` for non-partitioned assets and equals
`asset.partitions_def.get_serializable_unique_identifier()` for partitioned
ones. Both callers use `partitions_def_identifier` to group results:

- Schedule groups by `(partitions_def_identifier, partition_key)` and forms
  `run_key=f"{partitions_def_identifier or ''}_{partition_key or ''}"`.
- Sensor derives `job_name` from `partitions_def_identifier` (non-partitioned →
  `f"{base_job_name}_None"`, partitioned →
  `f"{base_job_name}_{partitions_def_identifier}"`), then groups by
  `(job_name, partition_key)` and forms
  `run_key=f"{job_name}_{partition_key}_{datetime.now().timestamp()}"`.

**Run-key migration note:** The schedule previously stored `partition_key = ""`
for non-partitioned assets, producing `run_key = "_"`. After normalization,
`partition_key = None` and `run_key = f"{None or ''}_{None or ''}" = "_"` — the
emitted run-key string is identical. The field value in `StalenessResult`
changes (`""` → `None`) but Dagster run-deduplication state is unaffected. The
sensor's run key already included a timestamp, making it inherently unique per
tick — no impact there either.

### `evaluate_asset_staleness()`

```python
def evaluate_asset_staleness(
    asset_selection: list[AssetsDefinition],
    execution_timezone: ZoneInfo,
    instance: DagsterInstance,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log,
    limit_monthly_partitions: int | None = None,
) -> list[StalenessResult]:
```

`connection` is the open `oracledb.Connection` yielded by
`powerschool_connection()`. `db_powerschool` is the resource used to execute
queries via
`db_powerschool.execute_query(connection=connection, query=..., prefetch_rows=2, array_size=1)`.
Both are required: `PowerSchoolODBCResource` is a stateless Dagster
`ConfigurableResource` that does not own a connection — the connection must be
created externally and passed in. `evaluate_asset_staleness` must be called
**inside** the `with powerschool_connection(...)` block:

```python
with powerschool_connection(ssh_resource, db_resource, log) as connection:
    results = evaluate_asset_staleness(..., connection=connection, ...)
```

`execute_query()` returns `list[tuple]` for COUNT queries. A `COUNT(*)` query
always returns exactly one row; results are unpacked as
`[(count,)] = db_powerschool.execute_query(...)` to extract the single integer.

`limit_monthly_partitions` controls how many monthly partition keys are checked:
`None` checks all (sensor behavior); an integer `n` checks the `n` most recently
dated keys. `partition_keys` from Dagster's `get_partition_keys()` is sorted
chronologically ascending (oldest first), so `partition_keys[-n:]` yields the
`n` most recent. The slice is applied in `evaluate_asset_staleness` before
calling `_evaluate_partitioned`: if the asset has a
`MonthlyPartitionsDefinition` and `limit_monthly_partitions is not None`,
`partition_keys = partition_keys[-n:]`. Fiscal-year and other types are not
sliced. The schedule passes `12`.

`instance` is queried via:

- `instance.get_latest_materialization_events(asset_keys)` — bulk lookup for
  non-partitioned assets; returns `dict[AssetKey, EventLogEntry]`
- `instance.fetch_materializations(records_filter=AssetRecordsFilter(...), limit=1)`
  — per-partition lookup; returns an object with
  `.records: list[EventLogRecord]`

Materialization metadata is read from
`event.asset_materialization.metadata["records"].value` (full-table row count at
the time of materialization, an `int`) and
`event.asset_materialization.metadata["latest_materialization_timestamp"].value`
(a `float` Unix timestamp).

`table_name` and `partition_column` are read from asset metadata via
`asset.metadata_by_key[asset.key]["table_name"]` and
`asset.metadata_by_key[asset.key]["partition_column"]` respectively.
`partition_column` is `None` for assets where no column-level change tracking
applies.

Internally structured with private helpers to keep nesting ≤3:

#### `_evaluate_non_partitioned`

```python
_evaluate_non_partitioned(
    asset, latest_event, connection, db_powerschool, execution_timezone, log
) -> StalenessResult | None
```

Three sequential checks using early returns. `metadata["records"]` is always
present for materialized assets (set by `build_powerschool_table_asset()` in
every `Output`); its absence indicates a corrupted event and is treated as a
programming error (will raise `KeyError`). `materialization_count` is the Oracle
`COUNT(*)` of the full table at the time of the last materialization, written to
`metadata["records"]` by the asset factory. A zero value is valid (the table was
empty at materialization time).

1. `latest_event is None` → return `StalenessResult` (never materialized)
2. `partition_column is not None`: call
   `get_query_text(table=table_name, column=partition_column, start_value=format_oracle_timestamp(latest_materialization_timestamp, execution_timezone))`
   to count rows modified since last materialization. If `modified_count > 0` →
   return `StalenessResult`. If `modified_count == 0`, fall through to check 3.
3. Call `get_query_text(table=table_name, column=None)` to get total table row
   count. If `table_count != materialization_count` → return `StalenessResult`
   (`materialization_count` is the full-table row count stored in
   `metadata["records"]` at last materialization)

Returns `None` if not stale.

#### `_evaluate_partitioned`

```python
_evaluate_partitioned(
    asset, partition_keys, connection, db_powerschool,
    execution_timezone, instance, log
) -> list[StalenessResult]
```

Determines `first_partition_key` and `last_partition_key` from
`asset.partitions_def.get_first_partition_key()` and
`asset.partitions_def.get_last_partition_key()` — these refer to the
chronologically oldest and most recent keys in the **full** partition
definition, not the iterated slice.

Iterates `partition_keys`, delegates each to `_evaluate_partition()`, collects
non-`None` results.

#### `_evaluate_partition`

```python
_evaluate_partition(
    asset, partition_key, first_partition_key, last_partition_key,
    connection, db_powerschool, execution_timezone, instance, log
) -> StalenessResult | None
```

Four sequential checks using early returns. Check 1 (skip-first) runs before the
materialization lookup so the first partition is always excluded, even if it has
never been materialized:

1. `partition_key == first_partition_key` → return `None` (skip: the first
   partition may contain historical records with null values in the partition
   column and is excluded from staleness checks by design). **Edge case:** if
   `first_partition_key == last_partition_key` (single-partition asset), this
   check fires first and the partition is skipped entirely — by design.
2. Partition never materialized (`fetch_materializations` returns no records) →
   return `StalenessResult`
3. `partition_key == last_partition_key`: call
   `get_query_text(table=table_name, column=partition_column, start_value=format_oracle_timestamp(latest_materialization_timestamp, execution_timezone))`
   to count rows modified since last materialization. If `modified_count > 0` →
   return `StalenessResult`
4. Call
   `get_query_text(table=table_name, column=partition_column, start_value=start_value, end_value=end_value)`
   (window from `get_partition_window(partition_key, asset.partitions_def)`) to
   count partition rows. `partitions_def` is derived from `asset.partitions_def`
   inside the function. If `partition_count > 0` and
   `partition_count != materialization_count` → return `StalenessResult`. The
   `partition_count > 0` guard means "if Oracle has no rows for this partition
   window, it is not stale" (the absence of data is not a staleness signal).
   When `materialization_count == 0` and `partition_count > 0`, the check fires
   — data has appeared since a zero-row materialization, which is stale.

Returns `None` if not stale.

### `schedules.py` (after)

~50 lines. Sets up the `@schedule`, opens a connection via
`powerschool_connection()`, calls
`evaluate_asset_staleness(limit_monthly_partitions=12)`, groups results by
`(partitions_def_identifier, partition_key)`, yields `RunRequest`s.

### `sensors.py` (after)

~70 lines. Sets up the `@sensor` and jobs, opens a connection via
`powerschool_connection()`, calls
`evaluate_asset_staleness(limit_monthly_partitions=None)`, groups results by
`(job_name, partition_key)`, returns `SensorResult`. Always returns
`SensorResult` (never `SkipReason`) — empty `run_requests` when nothing is
stale. The current code declares `-> SensorResult | SkipReason` but never
returns `SkipReason`; the refactor drops it from the return type.

### `assets.py` (after)

~120 lines (from ~164). The factory `build_powerschool_table_asset()` produces
one asset function per call — there is one SSH tunnel lifecycle and one
partition window calculation per factory invocation. Both are replaced:

1. SSH tunnel + connection lifecycle →
   `powerschool_connection(ssh_powerschool, db_powerschool, context.log)`
2. Partition window calculation →
   `get_partition_window(context.partition_key, partitions_def)` where
   `partitions_def` is the closure variable from the factory

Factory signature and asset metadata are unchanged.

## Behavioral Differences Reconciled

| Aspect                          | Before                                                      | After                                                                            |
| ------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Monthly partition limit         | Schedule: `[-12:]`; Sensor: all                             | `limit_monthly_partitions` parameter; schedule passes `12`, sensor passes `None` |
| Exception logging               | Schedule: `except` logs + re-raises; Sensor: `finally` only | `powerschool_connection()` logs in `except`, cleans up in `finally`              |
| Non-partitioned `partition_key` | Schedule: `""`; Sensor: `None`                              | Normalized to `None`; run-key format unchanged (see migration note)              |

## Testing

All Python files under `src/teamster/libraries/powerschool/sis/odbc/` must have
unit tests. Test files live in `tests/libraries/powerschool/sis/odbc/`.

### `utils.py`

- **`format_oracle_timestamp()`** — given a float + timezone, assert the correct
  Oracle-compatible ISO string
- **`get_partition_window()`** — given a partition key + each supported
  `partitions_def` type, assert correct `(start_value, end_value)` strings;
  assert `TypeError` for unsupported types
- **`get_query_text()`** — assert correct SQL for each branch (no column,
  start-only, start+end)
- **`evaluate_asset_staleness()`** — mock
  `instance.get_latest_materialization_events()` and
  `instance.fetch_materializations()` for materialization lookups; mock
  `db_powerschool.execute_query()` to return controlled COUNT results; assert
  correct `list[StalenessResult]` for each staleness condition:
  - Non-partitioned: never materialized
  - Non-partitioned: modified count > 0
  - Non-partitioned: table count mismatch
  - Partitioned: never materialized
  - Partitioned: skip first partition (assert absent from results)
  - Partitioned: last partition modified count > 0
  - Partitioned: partition count mismatch
  - `limit_monthly_partitions` slicing: only the last `n` monthly partitions are
    checked
  - Non-partitioned with `partition_column` set: modified count == 0 but table
    count mismatch → stale (verifies check 2 falls through to check 3)
- **`powerschool_connection()`** — mock SSH tunnel and DB connection to verify
  cleanup on success, on connection failure, and on query error

### `schedules.py`

- **`build_powerschool_sis_asset_schedule()`** — mock
  `evaluate_asset_staleness()` to return controlled `StalenessResult` lists;
  assert correct `RunRequest` grouping, run keys, and partition keys

### `sensors.py`

- **`build_powerschool_asset_sensor()`** — mock `evaluate_asset_staleness()` to
  return controlled `StalenessResult` lists; assert correct `SensorResult` with
  expected `RunRequest` grouping, job names, and run keys

### `assets.py`

- **`build_powerschool_table_asset()`** — mock SSH tunnel, DB connection, and
  `execute_query()` to return a fixture Avro file; assert correct `Output`
  metadata (records, digest, timestamp); test partition window delegation to
  `get_partition_window()`

### `resources.py`

- **`PowerSchoolODBCResource.execute_query()`** — mock `oracledb.Connection` and
  cursor; assert correct return for tuple-mode (fetchall) and avro-mode (file
  output); verify cursor prefetchrows/arraysize are set
- **`PowerSchoolODBCResource.connect()`** — mock `oracledb.connect()`; assert
  connection returned with correct params
- **`PowerSchoolODBCResource.result_to_avro()`** — mock cursor fetchmany; assert
  Avro file written with correct schema and records

### Existing integration tests

Reevaluate the existing integration tests in `tests/` for best practices:

- `tests/assets/test_assets_powerschool_sis.py`
- `tests/resources/test_resource_powerschool_sis.py`
- `tests/schedules/test_schedules_powerschool_sis.py`
- `tests/sensors/test_sensors_powerschool_sis.py`

Review for: proper assertions (not just "runs without error"), clear test names,
appropriate use of fixtures, separation of unit vs integration concerns, and
removal of dead code. Refactor or archive as needed.

## Docstrings

All Python files under `src/teamster/libraries/powerschool/sis/odbc/` must have
Google-style docstrings on all public functions, classes, and the module itself.

## Expected Outcome

Line counts are estimates, not acceptance criteria. The nesting ≤3 rule is the
binding constraint.

|                  | Before                                     | After                              |
| ---------------- | ------------------------------------------ | ---------------------------------- |
| `schedules.py`   | ~330 lines, 7 nesting levels               | ~50 lines, ≤3 nesting levels       |
| `sensors.py`     | ~360 lines, 7 nesting levels               | ~70 lines, ≤3 nesting levels       |
| `assets.py`      | ~164 lines, inline lifecycle + window code | ~120 lines, delegates to utilities |
| `utils.py`       | ~30 lines                                  | ~150 lines (all shared logic)      |
| Duplicated lines | ~250                                       | 0                                  |
