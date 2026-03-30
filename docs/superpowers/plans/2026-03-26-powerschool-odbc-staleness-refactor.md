# PowerSchool ODBC Staleness Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deduplicate ~250 lines of staleness detection logic shared between
`schedules.py` and `sensors.py`, reduce nesting from 7 to ≤3 levels, add full
unit test coverage and docstrings to all Python files in the module.

**Architecture:** Extract shared SSH lifecycle, timestamp formatting, partition
window calculation, and staleness evaluation into `utils.py`. Thin out
`schedules.py`, `sensors.py`, and `assets.py` to delegate to utilities. Add unit
tests for every file. Add Google-style docstrings to every public symbol.

**Tech Stack:** Python 3.13, Dagster, oracledb, dateutil, fastavro, pytest

**Spec:**
`docs/superpowers/specs/2026-03-20-powerschool-odbc-staleness-refactor-design.md`

**Issue:** [#2342](https://github.com/TEAMSchools/teamster/issues/2342)

---

## File Map

| File                                                       | Action | Responsibility                                                                                                                                           |
| ---------------------------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/teamster/libraries/powerschool/sis/odbc/utils.py`     | Modify | Add `powerschool_connection()`, `format_oracle_timestamp()`, `get_partition_window()`, `StalenessResult`, `evaluate_asset_staleness()` + private helpers |
| `src/teamster/libraries/powerschool/sis/odbc/schedules.py` | Modify | Thin to ~50 lines: `@schedule` + grouping only                                                                                                           |
| `src/teamster/libraries/powerschool/sis/odbc/sensors.py`   | Modify | Thin to ~70 lines: `@sensor` + job setup + grouping only                                                                                                 |
| `src/teamster/libraries/powerschool/sis/odbc/assets.py`    | Modify | Replace inline lifecycle/window code with `powerschool_connection()` + `get_partition_window()`                                                          |
| `src/teamster/libraries/powerschool/sis/odbc/resources.py` | Modify | Docstrings only (no implementation changes)                                                                                                              |
| `src/teamster/libraries/powerschool/sis/odbc/schema.py`    | Modify | Docstrings only                                                                                                                                          |
| `tests/libraries/powerschool/sis/odbc/test_utils.py`       | Create | Unit tests for all `utils.py` functions                                                                                                                  |
| `tests/libraries/powerschool/sis/odbc/test_schedules.py`   | Create | Unit tests for schedule factory                                                                                                                          |
| `tests/libraries/powerschool/sis/odbc/test_sensors.py`     | Create | Unit tests for sensor factory                                                                                                                            |
| `tests/libraries/powerschool/sis/odbc/test_assets.py`      | Create | Unit tests for asset factory                                                                                                                             |
| `tests/libraries/powerschool/sis/odbc/test_resources.py`   | Create | Unit tests for resource methods                                                                                                                          |

---

### Task 1: Test and docstring `get_query_text()` (existing)

The existing function in `utils.py` has no tests or docstrings. Test it first
before modifying the file.

**Files:**

- Read: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Create: `tests/libraries/powerschool/sis/odbc/test_utils.py`

- [ ] **Step 1: Write tests for `get_query_text()`**

```python
"""Unit tests for PowerSchool SIS ODBC utilities."""

from teamster.libraries.powerschool.sis.odbc.utils import get_query_text


class TestGetQueryText:
    def test_no_column_returns_full_table_count(self):
        result = get_query_text(table="STUDENTS", column=None)
        assert str(result) == "SELECT COUNT(*) FROM STUDENTS"

    def test_start_value_only_returns_gte_filter(self):
        result = get_query_text(
            table="STUDENTS",
            column="WHENMODIFIED",
            start_value="2024-07-01T00:00:00.000000",
        )
        sql = str(result)
        assert "COUNT(*)" in sql
        assert "STUDENTS" in sql
        assert "WHENMODIFIED >=" in sql
        assert "TO_TIMESTAMP('2024-07-01T00:00:00.000000'" in sql

    def test_start_and_end_value_returns_between_filter(self):
        result = get_query_text(
            table="STUDENTS",
            column="WHENMODIFIED",
            start_value="2024-07-01T00:00:00.000000",
            end_value="2025-06-30T23:59:59.999999",
        )
        sql = str(result)
        assert "BETWEEN" in sql
        assert "TO_TIMESTAMP('2024-07-01T00:00:00.000000'" in sql
        assert "TO_TIMESTAMP('2025-06-30T23:59:59.999999'" in sql
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestGetQueryText -v
```

Expected: PASS (testing existing code)

- [ ] **Step 3: Add module docstring and `get_query_text()` docstring to
      `utils.py`**

Add to `utils.py`:

```python
"""PowerSchool SIS ODBC shared utilities.

Context managers, timestamp formatting, partition window calculation,
and staleness evaluation logic shared across assets, schedules, and sensors.
"""
```

Add Google-style docstring to `get_query_text()`:

```python
def get_query_text(
    table: str,
    column: str | None,
    start_value: str | None = None,
    end_value: str | None = None,
):
    """Build a SQLAlchemy text clause for an Oracle COUNT query.

    Args:
        table: Oracle table name.
        column: Column to filter on. None for full table count.
        start_value: ISO timestamp string for >= or BETWEEN start.
        end_value: ISO timestamp string for BETWEEN end. Requires start_value.

    Returns:
        SQLAlchemy TextClause wrapping the COUNT query.
    """
```

- [ ] **Step 4: Run tests to confirm nothing broke**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git add tests/libraries/powerschool/sis/odbc/test_utils.py
git commit -m "test: add unit tests for get_query_text"
```

---

### Task 2: Add `format_oracle_timestamp()` to `utils.py` (TDD)

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Modify: `tests/libraries/powerschool/sis/odbc/test_utils.py`

- [ ] **Step 1: Write the failing test**

Append to `test_utils.py`:

```python
from zoneinfo import ZoneInfo

from teamster.libraries.powerschool.sis.odbc.utils import format_oracle_timestamp


class TestFormatOracleTimestamp:
    def test_formats_utc_timestamp(self):
        # 2024-07-01 12:00:00 UTC
        ts = 1719835200.0
        result = format_oracle_timestamp(ts, ZoneInfo("UTC"))
        assert result == "2024-07-01T12:00:00.000000"

    def test_formats_eastern_timestamp(self):
        # 2024-07-01 12:00:00 UTC = 2024-07-01 08:00:00 EDT
        ts = 1719835200.0
        result = format_oracle_timestamp(ts, ZoneInfo("America/New_York"))
        assert result == "2024-07-01T08:00:00.000000"

    def test_preserves_microseconds(self):
        ts = 1719835200.123456
        result = format_oracle_timestamp(ts, ZoneInfo("UTC"))
        assert result.endswith(".123456")

    def test_strips_timezone_info(self):
        ts = 1719835200.0
        result = format_oracle_timestamp(ts, ZoneInfo("America/New_York"))
        assert "+" not in result
        assert "-04" not in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestFormatOracleTimestamp -v
```

Expected: FAIL with `ImportError: cannot import name 'format_oracle_timestamp'`

- [ ] **Step 3: Write minimal implementation**

Add to `utils.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo


def format_oracle_timestamp(timestamp: float, tz: ZoneInfo) -> str:
    """Convert a Unix timestamp to an Oracle-compatible ISO string.

    Produces a timezone-naive ISO string at microsecond precision, suitable
    for Oracle's TO_TIMESTAMP function.

    Args:
        timestamp: Unix timestamp (seconds since epoch).
        tz: Timezone to localize the timestamp before stripping tzinfo.

    Returns:
        ISO 8601 string without timezone, e.g. '2024-07-01T12:00:00.000000'.
    """
    return (
        datetime.fromtimestamp(timestamp, tz=tz)
        .replace(tzinfo=None)
        .isoformat(timespec="microseconds")
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestFormatOracleTimestamp -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat: add format_oracle_timestamp to ODBC utils"
```

---

### Task 3: Add `get_partition_window()` to `utils.py` (TDD)

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Modify: `tests/libraries/powerschool/sis/odbc/test_utils.py`

- [ ] **Step 1: Write the failing test**

Append to `test_utils.py`:

```python
import pytest
from dagster import MonthlyPartitionsDefinition

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.odbc.utils import get_partition_window


class TestGetPartitionWindow:
    def test_fiscal_year_window(self):
        partitions_def = FiscalYearPartitionsDefinition(
            start_month=7, start_date="2023-07-01"
        )
        start, end = get_partition_window("2024-07-01", partitions_def)
        assert start == "2024-07-01T00:00:00.000000"
        assert end == "2025-06-30T23:59:59.999999"

    def test_monthly_window(self):
        partitions_def = MonthlyPartitionsDefinition(start_date="2024-01-01")
        start, end = get_partition_window("2024-07-01", partitions_def)
        assert start == "2024-07-01T00:00:00.000000"
        assert end == "2024-07-31T23:59:59.999999"

    def test_monthly_february_leap_year(self):
        partitions_def = MonthlyPartitionsDefinition(start_date="2024-01-01")
        start, end = get_partition_window("2024-02-01", partitions_def)
        assert start == "2024-02-01T00:00:00.000000"
        assert end == "2024-02-29T23:59:59.999999"

    def test_monthly_february_non_leap_year(self):
        partitions_def = MonthlyPartitionsDefinition(start_date="2023-01-01")
        start, end = get_partition_window("2023-02-01", partitions_def)
        assert start == "2023-02-01T00:00:00.000000"
        assert end == "2023-02-28T23:59:59.999999"

    def test_unsupported_type_raises_type_error(self):
        from dagster import DailyPartitionsDefinition

        partitions_def = DailyPartitionsDefinition(start_date="2024-01-01")
        with pytest.raises(TypeError, match="Unsupported partitions_def type"):
            get_partition_window("2024-07-01", partitions_def)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestGetPartitionWindow -v
```

Expected: FAIL with `ImportError: cannot import name 'get_partition_window'`

- [ ] **Step 3: Write minimal implementation**

Add to `utils.py`:

```python
from dagster import MonthlyPartitionsDefinition, TimeWindowPartitionsDefinition
from dateutil.relativedelta import relativedelta

from teamster.core.utils.classes import FiscalYearPartitionsDefinition


def get_partition_window(
    partition_key: str, partitions_def: TimeWindowPartitionsDefinition
) -> tuple[str, str]:
    """Compute Oracle-compatible ISO timestamp bounds for a partition window.

    Args:
        partition_key: ISO date string for the partition start (e.g. '2024-07-01').
        partitions_def: Dagster partitions definition (FiscalYear or Monthly).

    Returns:
        Tuple of (start_value, end_value) as timezone-naive ISO strings at
        microsecond precision.

    Raises:
        TypeError: If partitions_def is not FiscalYearPartitionsDefinition or
            MonthlyPartitionsDefinition.
    """
    partition_start = datetime.fromisoformat(partition_key)

    if isinstance(partitions_def, FiscalYearPartitionsDefinition):
        date_add = relativedelta(years=1)
    elif isinstance(partitions_def, MonthlyPartitionsDefinition):
        date_add = relativedelta(months=1)
    else:
        raise TypeError(
            f"Unsupported partitions_def type: {type(partitions_def).__name__}"
        )

    partition_end = (
        partition_start + date_add - relativedelta(days=1)
    ).replace(hour=23, minute=59, second=59, microsecond=999999)

    start_value = partition_start.replace(tzinfo=None).isoformat(
        timespec="microseconds"
    )
    end_value = partition_end.replace(tzinfo=None).isoformat(
        timespec="microseconds"
    )

    return start_value, end_value
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestGetPartitionWindow -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat: add get_partition_window to ODBC utils"
```

---

### Task 4: Add `powerschool_connection()` to `utils.py` (TDD)

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Modify: `tests/libraries/powerschool/sis/odbc/test_utils.py`

- [ ] **Step 1: Write the failing test**

Append to `test_utils.py`:

```python
from unittest.mock import MagicMock, patch

from teamster.libraries.powerschool.sis.odbc.utils import powerschool_connection


class TestPowerschoolConnection:
    def _make_mocks(self):
        ssh = MagicMock()
        ssh.remote_host = "ps.example.com"
        tunnel = MagicMock()
        ssh.open_ssh_tunnel.return_value = tunnel

        db = MagicMock()
        conn = MagicMock()
        db.connect.return_value = conn

        log = MagicMock()

        return ssh, db, log, tunnel, conn

    def test_yields_connection_and_cleans_up(self):
        ssh, db, log, tunnel, conn = self._make_mocks()

        with powerschool_connection(ssh, db, log) as connection:
            assert connection is conn

        conn.close.assert_called_once()
        tunnel.kill.assert_called_once()

    def test_connection_failure_kills_tunnel(self):
        ssh, db, log, tunnel, conn = self._make_mocks()
        db.connect.side_effect = RuntimeError("connection refused")

        with pytest.raises(RuntimeError, match="connection refused"):
            with powerschool_connection(ssh, db, log):
                pass  # pragma: no cover

        tunnel.kill.assert_called_once()
        conn.close.assert_not_called()

    def test_query_error_logs_and_cleans_up(self):
        ssh, db, log, tunnel, conn = self._make_mocks()

        with pytest.raises(ValueError, match="bad query"):
            with powerschool_connection(ssh, db, log):
                raise ValueError("bad query")

        log.exception.assert_called_once()
        conn.close.assert_called_once()
        tunnel.kill.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestPowerschoolConnection -v
```

Expected: FAIL with `ImportError: cannot import name 'powerschool_connection'`

- [ ] **Step 3: Write minimal implementation**

Add to `utils.py`:

```python
from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def powerschool_connection(
    ssh_resource, db_resource, log
) -> Generator[object, None, None]:
    """Open an SSH tunnel and Oracle connection, with guaranteed cleanup.

    Opens the SSH tunnel first, then the database connection. On success,
    yields the connection. Cleans up both on exit.

    If the connection fails, the tunnel is killed immediately. If an error
    occurs during query execution, it is logged before re-raising. Connection
    failures propagate without logging (Dagster handles them at the run level).

    Args:
        ssh_resource: SSHResource with open_ssh_tunnel() method.
        db_resource: PowerSchoolODBCResource with connect() method.
        log: Dagster logger (context.log).

    Yields:
        Open oracledb.Connection.
    """
    log.info(f"Opening SSH tunnel to {ssh_resource.remote_host}")
    ssh_tunnel = ssh_resource.open_ssh_tunnel()
    try:
        connection = db_resource.connect()
    except Exception:
        ssh_tunnel.kill()
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py::TestPowerschoolConnection -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat: add powerschool_connection context manager to ODBC utils"
```

---

### Task 5: Add `StalenessResult` and `evaluate_asset_staleness()` to `utils.py` (TDD)

This is the largest task. The function has private helpers
`_evaluate_non_partitioned`, `_evaluate_partitioned`, and `_evaluate_partition`.
Tests are written against the public `evaluate_asset_staleness()` function.

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Modify: `tests/libraries/powerschool/sis/odbc/test_utils.py`

- [ ] **Step 1: Write test fixtures and helpers**

Append to `test_utils.py`:

```python
from dataclasses import dataclass
from unittest.mock import PropertyMock

from dagster import AssetKey, AssetsDefinition

from teamster.libraries.powerschool.sis.odbc.utils import (
    StalenessResult,
    evaluate_asset_staleness,
)


def _make_asset(
    key: str,
    table_name: str,
    partition_column: str | None = None,
    partitions_def=None,
):
    """Build a minimal mock AssetsDefinition for testing."""
    asset_key = AssetKey([key])
    asset = MagicMock(spec=AssetsDefinition)
    asset.key = asset_key
    asset.partitions_def = partitions_def
    asset.metadata_by_key = {
        asset_key: {
            "table_name": table_name,
            "partition_column": partition_column,
        }
    }
    return asset


def _make_materialization_event(records: int, timestamp: float):
    """Build a mock materialization event with metadata."""
    metadata = {
        "records": MagicMock(value=records),
        "latest_materialization_timestamp": MagicMock(value=timestamp),
    }
    mat = MagicMock()
    mat.metadata = metadata
    event = MagicMock()
    event.asset_materialization = mat
    return event


def _make_event_records(records_list):
    """Build a mock fetch_materializations result."""
    result = MagicMock()
    result.records = records_list
    return result
```

- [ ] **Step 2: Write non-partitioned staleness tests**

Append to `test_utils.py`:

```python
class TestEvaluateAssetStalenessNonPartitioned:
    def test_never_materialized(self):
        asset = _make_asset("test", "STUDENTS")
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: None,
        }
        db = MagicMock()
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert len(results) == 1
        assert results[0].asset_key == asset.key
        assert results[0].partitions_def_identifier is None
        assert results[0].partition_key is None

    def test_modified_count_gt_zero(self):
        asset = _make_asset("test", "STUDENTS", partition_column="WHENMODIFIED")
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: event,
        }
        db = MagicMock()
        db.execute_query.return_value = [(5,)]
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert len(results) == 1
        assert results[0].asset_key == asset.key

    def test_table_count_mismatch(self):
        asset = _make_asset("test", "STUDENTS")
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: event,
        }
        db = MagicMock()
        # table count != materialization count
        db.execute_query.return_value = [(150,)]
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert len(results) == 1

    def test_not_stale(self):
        asset = _make_asset("test", "STUDENTS")
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: event,
        }
        db = MagicMock()
        # table count matches
        db.execute_query.return_value = [(100,)]
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert len(results) == 0

    def test_modified_count_zero_falls_through_to_table_count(self):
        """partition_column set, modified_count == 0, table count mismatch."""
        asset = _make_asset("test", "STUDENTS", partition_column="WHENMODIFIED")
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: event,
        }
        db = MagicMock()
        # first call: modified count = 0; second call: table count = 150
        db.execute_query.side_effect = [[(0,)], [(150,)]]
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert len(results) == 1
        assert db.execute_query.call_count == 2
```

- [ ] **Step 3: Write partitioned staleness tests**

Append to `test_utils.py`:

```python
class TestEvaluateAssetStalenessPartitioned:
    def _make_monthly_partitions_def(self):
        return MonthlyPartitionsDefinition(start_date="2024-01-01")

    def _make_partitioned_asset(self, partitions_def):
        asset = _make_asset(
            "test",
            "STOREDGRADES",
            partition_column="WHENMODIFIED",
            partitions_def=partitions_def,
        )
        return asset

    def test_never_materialized_partition(self):
        pdef = self._make_monthly_partitions_def()
        asset = self._make_partitioned_asset(pdef)
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: None,
        }
        # return no records for fetch_materializations
        instance.fetch_materializations.return_value = _make_event_records([])
        db = MagicMock()
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
            # only check 2 most recent to keep test fast
            limit_monthly_partitions=2,
        )

        # first partition skipped, remaining unmaterialized partitions returned
        for r in results:
            assert r.partition_key != pdef.get_first_partition_key()
        assert len(results) > 0

    def test_skip_first_partition(self):
        pdef = self._make_monthly_partitions_def()
        asset = self._make_partitioned_asset(pdef)
        first_key = pdef.get_first_partition_key()
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: None,
        }
        instance.fetch_materializations.return_value = _make_event_records([])
        db = MagicMock()
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert all(r.partition_key != first_key for r in results)

    def test_last_partition_modified_count_gt_zero(self):
        pdef = self._make_monthly_partitions_def()
        asset = self._make_partitioned_asset(pdef)
        last_key = pdef.get_last_partition_key()
        event = _make_materialization_event(records=50, timestamp=1719835200.0)
        event_record = MagicMock()
        event_record.asset_materialization = event.asset_materialization
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: None,
        }
        instance.fetch_materializations.return_value = _make_event_records(
            [event_record]
        )
        db = MagicMock()
        # modified count > 0 for last partition
        db.execute_query.return_value = [(10,)]
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
            limit_monthly_partitions=1,
        )

        last_results = [r for r in results if r.partition_key == last_key]
        assert len(last_results) == 1

    def test_partition_count_mismatch(self):
        pdef = MonthlyPartitionsDefinition(start_date="2024-06-01")
        asset = self._make_partitioned_asset(pdef)
        keys = pdef.get_partition_keys()
        # pick a non-first, non-last key
        mid_key = keys[1] if len(keys) > 2 else keys[-1]
        event = _make_materialization_event(records=50, timestamp=1719835200.0)
        event_record = MagicMock()
        event_record.asset_materialization = event.asset_materialization
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: None,
        }
        instance.fetch_materializations.return_value = _make_event_records(
            [event_record]
        )
        db = MagicMock()
        # partition count != materialization count (50)
        db.execute_query.return_value = [(75,)]
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
        )

        assert len(results) > 0

    def test_limit_monthly_partitions_slicing(self):
        pdef = MonthlyPartitionsDefinition(start_date="2024-01-01")
        asset = self._make_partitioned_asset(pdef)
        all_keys = pdef.get_partition_keys()
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {
            asset.key: None,
        }
        instance.fetch_materializations.return_value = _make_event_records([])
        db = MagicMock()
        conn = MagicMock()
        log = MagicMock()

        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=conn,
            db_powerschool=db,
            log=log,
            limit_monthly_partitions=3,
        )

        # only the last 3 partition keys should be checked (minus first if it
        # falls in the slice). The total results should not exceed 3.
        result_keys = {r.partition_key for r in results}
        expected_slice = set(all_keys[-3:])
        assert result_keys.issubset(expected_slice)
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py -k "Staleness" -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 5: Implement `StalenessResult` dataclass**

Add to `utils.py`:

```python
from dataclasses import dataclass

from dagster import AssetKey


@dataclass
class StalenessResult:
    """A stale asset or partition that needs re-materialization.

    Every entry in the list returned by evaluate_asset_staleness represents
    an asset/partition that is stale. Absence from the list means not stale.

    Attributes:
        asset_key: Dagster AssetKey of the stale asset.
        partitions_def_identifier: Serializable unique identifier for the
            partitions definition. None for non-partitioned assets.
        partition_key: Partition key string. None for non-partitioned assets.
    """

    asset_key: AssetKey
    partitions_def_identifier: str | None
    partition_key: str | None
```

- [ ] **Step 6: Implement `evaluate_asset_staleness()` and private helpers**

Add to `utils.py`:

```python
from dagster import (
    AssetRecordsFilter,
    AssetsDefinition,
    DagsterInstance,
    MonthlyPartitionsDefinition,
)
from dagster_shared import check

import oracledb

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource


def evaluate_asset_staleness(
    asset_selection: list[AssetsDefinition],
    execution_timezone: ZoneInfo,
    instance: DagsterInstance,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log,
    limit_monthly_partitions: int | None = None,
) -> list[StalenessResult]:
    """Evaluate which assets in the selection are stale.

    Queries the Oracle database to compare current row counts against the
    last materialization metadata. Must be called inside a
    powerschool_connection() context manager.

    Args:
        asset_selection: Assets to evaluate.
        execution_timezone: Timezone for timestamp formatting.
        instance: Dagster instance for materialization lookups.
        connection: Open oracledb connection (from powerschool_connection).
        db_powerschool: Resource for executing Oracle queries.
        log: Dagster logger.
        limit_monthly_partitions: If set, only check the N most recent
            monthly partition keys. None checks all. Does not affect
            fiscal-year partitions.

    Returns:
        List of StalenessResult for each stale asset/partition.
    """
    results: list[StalenessResult] = []
    asset_keys = [a.key for a in asset_selection]

    latest_events = instance.get_latest_materialization_events(asset_keys)

    for asset in asset_selection:
        if asset.partitions_def is None:
            latest_event = latest_events.get(asset.key)
            result = _evaluate_non_partitioned(
                asset, latest_event, connection, db_powerschool,
                execution_timezone, log,
            )
            if result is not None:
                results.append(result)
        else:
            partition_keys = asset.partitions_def.get_partition_keys()

            if (
                limit_monthly_partitions is not None
                and isinstance(asset.partitions_def, MonthlyPartitionsDefinition)
            ):
                partition_keys = partition_keys[-limit_monthly_partitions:]

            results.extend(
                _evaluate_partitioned(
                    asset, partition_keys, connection, db_powerschool,
                    execution_timezone, instance, log,
                )
            )

    return results


def _evaluate_non_partitioned(
    asset, latest_event, connection, db_powerschool, execution_timezone, log,
) -> StalenessResult | None:
    metadata = asset.metadata_by_key[asset.key]
    table_name = metadata["table_name"]
    partition_column = metadata["partition_column"]

    if latest_event is None:
        log.info(
            msg=f"{asset.key.to_python_identifier()} never materialized"
        )
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    mat_metadata = check.not_none(
        value=latest_event.asset_materialization
    ).metadata
    materialization_count = mat_metadata["records"].value

    if partition_column is not None:
        timestamp = check.inst(
            obj=mat_metadata["latest_materialization_timestamp"].value,
            ttype=float,
        )
        [(modified_count,)] = check.inst(
            db_powerschool.execute_query(
                connection=connection,
                query=get_query_text(
                    table=table_name,
                    column=partition_column,
                    start_value=format_oracle_timestamp(
                        timestamp, execution_timezone
                    ),
                ),
                prefetch_rows=2,
                array_size=1,
            ),
            list,
        )
        if modified_count > 0:
            log.info(
                msg=(
                    f"{asset.key.to_python_identifier()}\n"
                    f"modified count: {modified_count}"
                )
            )
            return StalenessResult(
                asset_key=asset.key,
                partitions_def_identifier=None,
                partition_key=None,
            )

    [(table_count,)] = check.inst(
        db_powerschool.execute_query(
            connection=connection,
            query=get_query_text(table=table_name, column=None),
            prefetch_rows=2,
            array_size=1,
        ),
        list,
    )
    if table_count != materialization_count:
        log.info(
            msg=(
                f"{asset.key.to_python_identifier()}\n"
                f"PS count ({table_count}) != "
                f"DB count ({materialization_count})"
            )
        )
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    return None


def _evaluate_partitioned(
    asset, partition_keys, connection, db_powerschool,
    execution_timezone, instance, log,
) -> list[StalenessResult]:
    first_partition_key = asset.partitions_def.get_first_partition_key()
    last_partition_key = asset.partitions_def.get_last_partition_key()

    results = []
    for partition_key in partition_keys:
        result = _evaluate_partition(
            asset, partition_key, first_partition_key, last_partition_key,
            connection, db_powerschool, execution_timezone, instance, log,
        )
        if result is not None:
            results.append(result)
    return results


def _evaluate_partition(
    asset, partition_key, first_partition_key, last_partition_key,
    connection, db_powerschool, execution_timezone, instance, log,
) -> StalenessResult | None:
    metadata = asset.metadata_by_key[asset.key]
    table_name = metadata["table_name"]
    partition_column = metadata["partition_column"]
    partitions_def_identifier = (
        asset.partitions_def.get_serializable_unique_identifier()
    )

    if partition_key == first_partition_key:
        return None

    event_records = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=asset.key, asset_partitions=[partition_key]
        ),
        limit=1,
    )

    if not event_records.records:
        log.info(
            msg=f"{asset.key.to_python_identifier()} never materialized"
        )
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=partitions_def_identifier,
            partition_key=partition_key,
        )

    mat_metadata = check.not_none(
        value=event_records.records[0].asset_materialization
    ).metadata

    if partition_key == last_partition_key:
        timestamp = check.inst(
            obj=mat_metadata["latest_materialization_timestamp"].value,
            ttype=float,
        )
        [(modified_count,)] = check.inst(
            db_powerschool.execute_query(
                connection=connection,
                query=get_query_text(
                    table=table_name,
                    column=partition_column,
                    start_value=format_oracle_timestamp(
                        timestamp, execution_timezone
                    ),
                ),
                prefetch_rows=2,
                array_size=1,
            ),
            list,
        )
        if modified_count > 0:
            log.info(
                msg=(
                    f"{asset.key.to_python_identifier()}\n{partition_key}\n"
                    f"modified count: {modified_count}"
                )
            )
            return StalenessResult(
                asset_key=asset.key,
                partitions_def_identifier=partitions_def_identifier,
                partition_key=partition_key,
            )

    start_value, end_value = get_partition_window(
        partition_key, asset.partitions_def
    )
    [(partition_count,)] = check.inst(
        db_powerschool.execute_query(
            connection=connection,
            query=get_query_text(
                table=table_name,
                column=partition_column,
                start_value=start_value,
                end_value=end_value,
            ),
            prefetch_rows=2,
            array_size=1,
        ),
        list,
    )

    materialization_count = mat_metadata["records"].value

    if partition_count > 0 and partition_count != materialization_count:
        log.info(
            msg=(
                f"{asset.key.to_python_identifier()}\n{partition_key}\n"
                f"PS count ({partition_count}) "
                f"!= DB count ({materialization_count})"
            )
        )
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=partitions_def_identifier,
            partition_key=partition_key,
        )

    return None
```

- [ ] **Step 7: Run all staleness tests**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_utils.py -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -u
git commit -m "feat: add StalenessResult and evaluate_asset_staleness to ODBC utils"
```

---

### Task 6: Refactor `schedules.py` to use shared utilities

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/schedules.py`
- Create: `tests/libraries/powerschool/sis/odbc/test_schedules.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for PowerSchool SIS ODBC schedule factory."""

from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from dagster import AssetKey

from teamster.libraries.powerschool.sis.odbc.utils import StalenessResult


class TestBuildPowerschoolSisAssetSchedule:
    @patch(
        "teamster.libraries.powerschool.sis.odbc.schedules.evaluate_asset_staleness"
    )
    @patch(
        "teamster.libraries.powerschool.sis.odbc.schedules.powerschool_connection"
    )
    def test_groups_run_requests_by_partitions_def_and_key(
        self, mock_conn_ctx, mock_eval
    ):
        from teamster.libraries.powerschool.sis.odbc.schedules import (
            build_powerschool_sis_asset_schedule,
        )

        mock_conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_eval.return_value = [
            StalenessResult(
                asset_key=AssetKey(["loc", "powerschool", "students"]),
                partitions_def_identifier=None,
                partition_key=None,
            ),
            StalenessResult(
                asset_key=AssetKey(["loc", "powerschool", "schools"]),
                partitions_def_identifier=None,
                partition_key=None,
            ),
        ]

        asset1 = MagicMock()
        asset1.key = AssetKey(["loc", "powerschool", "students"])
        asset2 = MagicMock()
        asset2.key = AssetKey(["loc", "powerschool", "schools"])

        schedule_fn = build_powerschool_sis_asset_schedule(
            code_location="loc",
            execution_timezone=ZoneInfo("America/New_York"),
            cron_schedule="0 0 * * *",
            asset_selection=[asset1, asset2],
        )

        context = MagicMock()
        ssh = MagicMock()
        db = MagicMock()

        run_requests = list(schedule_fn(context, ssh, db))

        # both non-partitioned assets grouped into one RunRequest
        assert len(run_requests) == 1
        assert run_requests[0].run_key == "_"
        assert len(run_requests[0].asset_selection) == 2

        # evaluate_asset_staleness called with limit_monthly_partitions=12
        mock_eval.assert_called_once()
        call_kwargs = mock_eval.call_args
        assert call_kwargs.kwargs.get("limit_monthly_partitions") == 12 or (
            len(call_kwargs.args) > 6 and call_kwargs.args[6] == 12
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_schedules.py -v
```

Expected: FAIL (schedule still has old implementation)

- [ ] **Step 3: Rewrite `schedules.py`**

Replace the full contents of `schedules.py` with:

```python
"""PowerSchool SIS ODBC asset schedule.

Defines a Dagster schedule that evaluates PowerSchool assets for staleness
and yields RunRequests for stale assets grouped by partition definition
and partition key.
"""

from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    schedule,
)

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import (
    evaluate_asset_staleness,
    powerschool_connection,
)
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_sis_asset_schedule(
    code_location: str,
    execution_timezone: ZoneInfo,
    cron_schedule: str,
    asset_selection: list[AssetsDefinition],
    max_runtime_seconds: int = (60 * 10),
):
    """Build a Dagster schedule that detects and rematerializes stale assets.

    Args:
        code_location: District code location identifier.
        execution_timezone: Timezone for schedule evaluation.
        cron_schedule: Cron expression for schedule frequency.
        asset_selection: Assets to monitor for staleness.
        max_runtime_seconds: Maximum run duration tag value.

    Returns:
        A Dagster schedule function.
    """

    @schedule(
        name=f"{code_location}__powerschool__sis__asset_job_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=str(execution_timezone),
        target=asset_selection,
    )
    def _schedule(
        context: ScheduleEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ):
        with powerschool_connection(
            ssh_powerschool, db_powerschool, context.log
        ) as connection:
            results = evaluate_asset_staleness(
                asset_selection=asset_selection,
                execution_timezone=execution_timezone,
                instance=context.instance,
                connection=connection,
                db_powerschool=db_powerschool,
                log=context.log,
                limit_monthly_partitions=12,
            )

        kwargs = [
            {
                "key": r.asset_key,
                "partitions_def": r.partitions_def_identifier or "",
                "partition_key": r.partition_key or "",
            }
            for r in results
        ]

        item_getter = itemgetter("partitions_def", "partition_key")

        for (partitions_def, partition_key), group in groupby(
            iterable=sorted(kwargs, key=item_getter), key=item_getter
        ):
            yield RunRequest(
                run_key=f"{partitions_def}_{partition_key}",
                asset_selection=[g["key"] for g in group],
                partition_key=partition_key or None,
                tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
            )

    return _schedule
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_schedules.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git add tests/libraries/powerschool/sis/odbc/test_schedules.py
git commit -m "refactor: rewrite schedules.py to use shared staleness evaluation"
```

---

### Task 7: Refactor `sensors.py` to use shared utilities

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/sensors.py`
- Create: `tests/libraries/powerschool/sis/odbc/test_sensors.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for PowerSchool SIS ODBC sensor factory."""

from collections import defaultdict
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from dagster import AssetKey

from teamster.libraries.powerschool.sis.odbc.utils import StalenessResult


class TestBuildPowerschoolAssetSensor:
    @patch(
        "teamster.libraries.powerschool.sis.odbc.sensors.evaluate_asset_staleness"
    )
    @patch(
        "teamster.libraries.powerschool.sis.odbc.sensors.powerschool_connection"
    )
    def test_returns_sensor_result_with_grouped_run_requests(
        self, mock_conn_ctx, mock_eval
    ):
        from teamster.libraries.powerschool.sis.odbc.sensors import (
            build_powerschool_asset_sensor,
        )

        mock_conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_eval.return_value = [
            StalenessResult(
                asset_key=AssetKey(["loc", "powerschool", "students"]),
                partitions_def_identifier=None,
                partition_key=None,
            ),
            StalenessResult(
                asset_key=AssetKey(["loc", "powerschool", "schools"]),
                partitions_def_identifier=None,
                partition_key=None,
            ),
        ]

        asset1 = MagicMock()
        asset1.key = AssetKey(["loc", "powerschool", "students"])
        asset1.partitions_def = None
        asset2 = MagicMock()
        asset2.key = AssetKey(["loc", "powerschool", "schools"])
        asset2.partitions_def = None

        sensor_fn = build_powerschool_asset_sensor(
            code_location="loc",
            execution_timezone=ZoneInfo("America/New_York"),
            asset_selection=[asset1, asset2],
        )

        context = MagicMock()
        ssh = MagicMock()
        db = MagicMock()

        result = sensor_fn(context, ssh, db)

        assert hasattr(result, "run_requests")
        assert len(result.run_requests) == 1
        assert len(result.run_requests[0].asset_selection) == 2
        assert "loc__powerschool__sis__asset_job_None" in result.run_requests[
            0
        ].job_name

        # evaluate_asset_staleness called with limit_monthly_partitions=None
        mock_eval.assert_called_once()
        call_kwargs = mock_eval.call_args
        assert call_kwargs.kwargs.get("limit_monthly_partitions") is None

    @patch(
        "teamster.libraries.powerschool.sis.odbc.sensors.evaluate_asset_staleness"
    )
    @patch(
        "teamster.libraries.powerschool.sis.odbc.sensors.powerschool_connection"
    )
    def test_empty_results_returns_sensor_result(self, mock_conn_ctx, mock_eval):
        from teamster.libraries.powerschool.sis.odbc.sensors import (
            build_powerschool_asset_sensor,
        )

        mock_conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_eval.return_value = []

        asset = MagicMock()
        asset.key = AssetKey(["loc", "powerschool", "students"])
        asset.partitions_def = None

        sensor_fn = build_powerschool_asset_sensor(
            code_location="loc",
            execution_timezone=ZoneInfo("America/New_York"),
            asset_selection=[asset],
        )

        result = sensor_fn(MagicMock(), MagicMock(), MagicMock())

        assert hasattr(result, "run_requests")
        assert len(result.run_requests) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_sensors.py -v
```

Expected: FAIL

- [ ] **Step 3: Rewrite `sensors.py`**

Replace the full contents of `sensors.py` with:

```python
"""PowerSchool SIS ODBC asset sensor.

Defines a Dagster sensor that evaluates PowerSchool assets for staleness
and returns a SensorResult with RunRequests for stale assets grouped by
job name and partition key.
"""

from collections import defaultdict
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetKey,
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import (
    evaluate_asset_staleness,
    powerschool_connection,
)
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_asset_sensor(
    code_location: str,
    execution_timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    minimum_interval_seconds: int | None = None,
    max_runtime_seconds: int = (60 * 5),
):
    """Build a Dagster sensor that detects and rematerializes stale assets.

    Args:
        code_location: District code location identifier.
        execution_timezone: Timezone for sensor evaluation.
        asset_selection: Assets to monitor for staleness.
        minimum_interval_seconds: Minimum seconds between sensor ticks.
        max_runtime_seconds: Maximum run duration tag value.

    Returns:
        A Dagster sensor function.
    """
    jobs = []
    keys_by_partitions_def = defaultdict(set[AssetKey])

    base_job_name = f"{code_location}__powerschool__sis__asset_job"

    for assets_def in asset_selection:
        keys_by_partitions_def[assets_def.partitions_def].add(assets_def.key)

    for partitions_def, keys in keys_by_partitions_def.items():
        if partitions_def is None:
            job_name = f"{base_job_name}_None"
        else:
            job_name = (
                f"{base_job_name}"
                f"_{partitions_def.get_serializable_unique_identifier()}"
            )

        jobs.append(define_asset_job(name=job_name, selection=list(keys)))

    @sensor(
        name=f"{base_job_name}_sensor",
        jobs=jobs,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ) -> SensorResult:
        with powerschool_connection(
            ssh_powerschool, db_powerschool, context.log
        ) as connection:
            results = evaluate_asset_staleness(
                asset_selection=asset_selection,
                execution_timezone=execution_timezone,
                instance=context.instance,
                connection=connection,
                db_powerschool=db_powerschool,
                log=context.log,
                limit_monthly_partitions=None,
            )

        kwargs = []
        for r in results:
            if r.partitions_def_identifier is None:
                job_name = f"{base_job_name}_None"
            else:
                job_name = f"{base_job_name}_{r.partitions_def_identifier}"

            kwargs.append(
                {
                    "asset_key": r.asset_key,
                    "job_name": job_name,
                    "partition_key": r.partition_key,
                }
            )

        run_requests = []
        item_getter = itemgetter("job_name", "partition_key")

        for (job_name, partition_key), group in groupby(
            iterable=sorted(kwargs, key=item_getter), key=item_getter
        ):
            run_requests.append(
                RunRequest(
                    run_key=(
                        f"{job_name}_{partition_key}"
                        f"_{datetime.now().timestamp()}"
                    ),
                    job_name=job_name,
                    partition_key=partition_key,
                    asset_selection=[g["asset_key"] for g in group],
                    tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                )
            )

        return SensorResult(run_requests=run_requests)

    return _sensor
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_sensors.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git add tests/libraries/powerschool/sis/odbc/test_sensors.py
git commit -m "refactor: rewrite sensors.py to use shared staleness evaluation"
```

---

### Task 8: Refactor `assets.py` to use shared utilities

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/assets.py`
- Create: `tests/libraries/powerschool/sis/odbc/test_assets.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for PowerSchool SIS ODBC asset factory."""

import pathlib
from unittest.mock import MagicMock, patch

from dagster import MonthlyPartitionsDefinition

from teamster.core.utils.classes import FiscalYearPartitionsDefinition


class TestBuildPowerschoolTableAsset:
    @patch(
        "teamster.libraries.powerschool.sis.odbc.assets.powerschool_connection"
    )
    def test_non_partitioned_asset_output_metadata(self, mock_conn_ctx, tmp_path):
        from teamster.libraries.powerschool.sis.odbc.assets import (
            build_powerschool_table_asset,
        )

        mock_conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # Create a minimal Avro file fixture
        import fastavro

        avro_path = tmp_path / "data.avro"
        schema = {"type": "record", "name": "test", "fields": [{"name": "id", "type": "int"}]}
        with avro_path.open("wb") as f:
            fastavro.writer(f, schema, [{"id": 1}, {"id": 2}], codec="snappy")

        db = MagicMock()
        db.execute_query.return_value = avro_path

        asset_def = build_powerschool_table_asset(
            code_location="loc",
            table_name="STUDENTS",
        )

        context = MagicMock()
        context.has_partition_key = False
        ssh = MagicMock()

        with patch("teamster.libraries.powerschool.sis.odbc.assets.check") as mock_check:
            mock_check.inst.return_value = avro_path
            result = asset_def.op.compute_fn(context, ssh_powerschool=ssh, db_powerschool=db)

        assert result.metadata["records"].value == 2
        assert "digest" in result.metadata
        assert "latest_materialization_timestamp" in result.metadata

    @patch(
        "teamster.libraries.powerschool.sis.odbc.assets.get_partition_window"
    )
    @patch(
        "teamster.libraries.powerschool.sis.odbc.assets.powerschool_connection"
    )
    def test_partitioned_asset_delegates_to_get_partition_window(
        self, mock_conn_ctx, mock_window
    ):
        from teamster.libraries.powerschool.sis.odbc.assets import (
            build_powerschool_table_asset,
        )

        mock_window.return_value = (
            "2024-07-01T00:00:00.000000",
            "2024-07-31T23:59:59.999999",
        )

        asset_def = build_powerschool_table_asset(
            code_location="loc",
            table_name="STOREDGRADES",
            partitions_def=MonthlyPartitionsDefinition(start_date="2024-01-01"),
            partition_column="WHENMODIFIED",
        )

        # Verify the asset was created with correct metadata
        asset_key = asset_def.key
        metadata = asset_def.metadata_by_key[asset_key]
        assert metadata["table_name"] == "STOREDGRADES"
        assert metadata["partition_column"] == "WHENMODIFIED"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_assets.py -v
```

Expected: FAIL (assets.py still uses inline code, imports don't exist yet)

- [ ] **Step 3: Rewrite `assets.py`**

Replace the full contents of `assets.py` with:

```python
"""PowerSchool SIS ODBC asset factory.

Builds Dagster assets that query PowerSchool's Oracle database via SSH tunnel
and serialize results to Avro files for downstream loading into BigQuery.
"""

import hashlib
import pathlib
from datetime import datetime
from io import BufferedReader

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    Output,
    TimeWindowPartitionsDefinition,
    asset,
)
from dagster_shared import check
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import (
    get_partition_window,
    powerschool_connection,
)
from teamster.libraries.ssh.resources import SSHResource


def hash_bytestr_iter(bytesiter, hasher):
    """Compute a hex digest by iterating over byte blocks.

    Args:
        bytesiter: Iterator yielding bytes objects.
        hasher: A hashlib hash object (e.g. hashlib.sha256()).

    Returns:
        Hex digest string.
    """
    for block in bytesiter:
        hasher.update(block)

    return hasher.hexdigest()


def file_as_blockiter(file: BufferedReader, size: int = 65536):
    """Yield fixed-size blocks from a file for hashing.

    Args:
        file: Open file in binary read mode.
        size: Block size in bytes.

    Yields:
        Bytes blocks of the specified size.
    """
    with file:
        block = file.read(size)
        while len(block) > 0:
            yield block
            block = file.read(size)


def build_powerschool_table_asset(
    code_location,
    table_name: str,
    partitions_def: TimeWindowPartitionsDefinition | None = None,
    partition_column: str | None = None,
    partition_size: int = 10000,
    prefetch_rows: int = 10000,
    array_size: int = 500000,
    select_columns: list[str] | None = None,
    op_tags: dict | None = None,
) -> AssetsDefinition:
    """Build a Dagster asset that queries a PowerSchool Oracle table.

    Args:
        code_location: District code location identifier.
        table_name: Oracle table name.
        partitions_def: Optional time-window partitions definition.
        partition_column: Column to filter by partition window.
        partition_size: Avro writer batch size.
        prefetch_rows: Oracle cursor prefetchrows setting.
        array_size: Oracle cursor arraysize setting.
        select_columns: Columns to select. Defaults to ['*'].
        op_tags: Optional Dagster op tags.

    Returns:
        A Dagster AssetsDefinition.
    """
    if select_columns is None:
        select_columns = ["*"]

    @asset(
        key=[code_location, "powerschool", table_name],
        metadata={
            "table_name": table_name,
            "partition_column": partition_column,
            "select_columns": select_columns,
            "op_tags": op_tags,
        },
        partitions_def=partitions_def,
        op_tags=op_tags,
        io_manager_key="io_manager_gcs_file",
        group_name="powerschool",
        kinds={"python"},
    )
    def _asset(
        context: AssetExecutionContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ):
        timestamp = datetime.now().timestamp()

        first_partition_key = (
            partitions_def.get_first_partition_key()
            if partitions_def is not None
            else None
        )

        if not context.has_partition_key:
            constructed_where = ""
        elif context.partition_key == first_partition_key:
            constructed_where = ""
        else:
            start_value, end_value = get_partition_window(
                context.partition_key, partitions_def
            )

            constructed_where = (
                f"{partition_column} BETWEEN "
                f"TO_TIMESTAMP('{start_value}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
                f"TO_TIMESTAMP('{end_value}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            )

        sql = (
            select(*[literal_column(col) for col in select_columns])
            .select_from(table(table_name))
            .where(text(constructed_where))
        )

        with powerschool_connection(
            ssh_powerschool, db_powerschool, context.log
        ) as connection:
            file_path = check.inst(
                obj=db_powerschool.execute_query(
                    connection=connection,
                    query=sql,
                    output_format="avro",
                    batch_size=partition_size,
                    prefetch_rows=prefetch_rows,
                    array_size=array_size,
                ),
                ttype=pathlib.Path,
            )

        with file_path.open(mode="rb") as f:
            num_records = sum(block.num_records for block in block_reader(f))
            digest = hash_bytestr_iter(
                bytesiter=file_as_blockiter(file=f), hasher=hashlib.sha256()
            )

        return Output(
            value=file_path,
            metadata={
                "records": num_records,
                "digest": digest,
                "latest_materialization_timestamp": timestamp,
            },
        )

    return _asset
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_assets.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git add tests/libraries/powerschool/sis/odbc/test_assets.py
git commit -m "refactor: rewrite assets.py to use shared utilities"
```

---

### Task 9: Add unit tests for `resources.py`

No implementation changes — only tests and docstrings.

**Files:**

- Read: `src/teamster/libraries/powerschool/sis/odbc/resources.py`
- Modify: `src/teamster/libraries/powerschool/sis/odbc/resources.py`
  (docstrings)
- Create: `tests/libraries/powerschool/sis/odbc/test_resources.py`

- [ ] **Step 1: Write tests**

```python
"""Unit tests for PowerSchool SIS ODBC resource."""

import pathlib
from unittest.mock import MagicMock, patch

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource


class TestPowerSchoolODBCResourceConnect:
    @patch("teamster.libraries.powerschool.sis.odbc.resources.oracledb")
    def test_connect_returns_connection(self, mock_oracledb):
        resource = PowerSchoolODBCResource(
            user="testuser",
            password="testpass",
            host="localhost",
            port="1521",
            service_name="PSPRODDB",
        )

        mock_ctx = MagicMock()
        mock_ctx.log = MagicMock()
        resource.setup_for_execution(mock_ctx)

        conn = resource.connect()

        mock_oracledb.connect.assert_called_once()
        assert conn is mock_oracledb.connect.return_value


class TestPowerSchoolODBCResourceExecuteQuery:
    @patch("teamster.libraries.powerschool.sis.odbc.resources.oracledb")
    def test_tuple_mode_returns_fetchall(self, mock_oracledb):
        resource = PowerSchoolODBCResource(
            user="testuser",
            password="testpass",
            host="localhost",
            port="1521",
            service_name="PSPRODDB",
        )

        mock_ctx = MagicMock()
        mock_ctx.log = MagicMock()
        resource.setup_for_execution(mock_ctx)

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [(100,)]

        from sqlalchemy import text

        result = resource.execute_query(
            connection=conn,
            query=text("SELECT COUNT(*) FROM STUDENTS"),
            prefetch_rows=2,
            array_size=1,
        )

        assert result == [(100,)]
        assert cursor.prefetchrows == 2
        assert cursor.arraysize == 1
        cursor.close.assert_called_once()

    @patch("teamster.libraries.powerschool.sis.odbc.resources.oracledb")
    def test_avro_mode_returns_path(self, mock_oracledb):
        resource = PowerSchoolODBCResource(
            user="testuser",
            password="testpass",
            host="localhost",
            port="1521",
            service_name="PSPRODDB",
        )

        mock_ctx = MagicMock()
        mock_ctx.log = MagicMock()
        resource.setup_for_execution(mock_ctx)

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.description = [
            ("ID", mock_oracledb.DB_TYPE_NUMBER, None, None, None, None, None),
        ]

        with patch.object(resource, "result_to_avro") as mock_avro:
            mock_avro.return_value = pathlib.Path("env/data.avro")

            from sqlalchemy import text

            result = resource.execute_query(
                connection=conn,
                query=text("SELECT * FROM STUDENTS"),
                output_format="avro",
                prefetch_rows=10000,
                array_size=500000,
            )

            assert isinstance(result, pathlib.Path)
            mock_avro.assert_called_once()
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_resources.py -v
```

Expected: PASS

- [ ] **Step 3: Add docstrings to `resources.py`**

Read the file, then add Google-style docstrings to:

- Module level
- `PowerSchoolODBCResource` class
- `setup_for_execution()`
- `connect()`
- `execute_query()`
- `result_to_avro()`

Do not change any implementation logic.

- [ ] **Step 4: Run tests again**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/test_resources.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git add tests/libraries/powerschool/sis/odbc/test_resources.py
git commit -m "docs: add unit tests and docstrings for ODBC resources"
```

---

### Task 10: Add docstring to `schema.py`

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/schema.py`

- [ ] **Step 1: Add module docstring**

Add to the top of `schema.py`:

```python
"""Oracle-to-Avro type mapping for PowerSchool SIS ODBC.

Maps oracledb column type names from cursor.description to Avro schema type
definitions. All fields are nullable (wrapped in a union with "null").
"""
```

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "docs: add module docstring to ODBC schema.py"
```

---

### Task 11: Review and refactor existing integration tests

**Files:**

- Read: `tests/assets/test_assets_powerschool_sis.py`
- Read: `tests/resources/test_resource_powerschool_sis.py`
- Read: `tests/schedules/test_schedules_powerschool_sis.py`
- Read: `tests/sensors/test_sensors_powerschool_sis.py`

- [ ] **Step 1: Read all four test files**

Evaluate each for:

- Proper assertions (not just "runs without error")
- Clear test names
- Appropriate use of fixtures
- Separation of unit vs integration concerns
- Dead code

- [ ] **Step 2: Refactor or archive as needed**

Apply changes based on review findings. Integration tests that require live
Oracle connections should remain in their current locations and be clearly
marked as integration tests. Remove dead code.

- [ ] **Step 3: Run the full test suite for the module**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/ -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "test: review and refactor existing PowerSchool integration tests"
```

---

### Task 12: Validate Dagster definitions and final verification

- [ ] **Step 1: Run all new unit tests**

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/ -v
```

Expected: all PASS

- [ ] **Step 2: Validate Dagster definitions for all affected code locations**

```bash
uv run dagster definitions validate -m teamster.code_locations.kippnewark.definitions
uv run dagster definitions validate -m teamster.code_locations.kippcamden.definitions
uv run dagster definitions validate -m teamster.code_locations.kippmiami.definitions
```

Expected: all valid

- [ ] **Step 3: Verify nesting depth ≤3 in all modified files**

Manually review `utils.py`, `schedules.py`, `sensors.py`, and `assets.py` for
maximum nesting depth. The binding constraint from the spec is ≤3 levels.

- [ ] **Step 4: Verify no duplicated staleness logic remains**

Grep for patterns that should now only exist in `utils.py`:

- `format_oracle_timestamp` — only imported, not defined, in schedules/sensors
- `get_partition_window` — only imported, not defined, in
  schedules/sensors/assets
- `relativedelta` — only imported in `utils.py`, not in schedules/sensors

- [ ] **Step 5: Final commit**

```bash
git add -u
git commit -m "chore: validate Dagster definitions after ODBC staleness refactor"
```
