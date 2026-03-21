# PowerSchool ODBC Staleness Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Extract shared staleness detection logic into utils.py, reducing
nesting from 7 to 3.

**Architecture:** New utilities (`format_oracle_timestamp`,
`get_partition_window`, `powerschool_connection`, `StalenessResult`,
`evaluate_asset_staleness`) are added to `utils.py` following TDD; then
`assets.py`, `schedules.py`, and `sensors.py` are refactored to call them. No
public API or output format changes.

**Tech Stack:** Python 3.13, Dagster, oracledb, dateutil.relativedelta, pytest,
unittest.mock

---

### Task 1: `format_oracle_timestamp` and `get_partition_window`

- [ ] **Step 1: Write failing tests**

```python
# tests/libraries/test_powerschool_odbc_utils.py
import pytest
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from dagster import MonthlyPartitionsDefinition
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.odbc.utils import (
    format_oracle_timestamp,
    get_partition_window,
)


def test_format_oracle_timestamp():
    tz = ZoneInfo("America/New_York")
    result = format_oracle_timestamp(1700000000.0, tz)
    assert result == "2023-11-14T17:13:20.000000"


def test_get_partition_window_fiscal_year():
    partitions_def = FiscalYearPartitionsDefinition(
        start_month=7, start_date="2020-07-01", timezone="UTC"
    )
    start, end = get_partition_window("2024-07-01", partitions_def)
    assert start == "2024-07-01T00:00:00.000000"
    assert end == "2025-06-30T23:59:59.999999"


def test_get_partition_window_monthly():
    partitions_def = MonthlyPartitionsDefinition(start_date="2024-01-01", timezone="UTC")
    start, end = get_partition_window("2024-07-01", partitions_def)
    assert start == "2024-07-01T00:00:00.000000"
    assert end == "2024-07-31T23:59:59.999999"


def test_get_partition_window_unsupported_raises():
    with pytest.raises(TypeError):
        get_partition_window("2024-07-01", MagicMock())
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/libraries/test_powerschool_odbc_utils.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement the functions**

Add to `src/teamster/libraries/powerschool/sis/odbc/utils.py` (new imports +
functions after `get_query_text`):

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import MonthlyPartitionsDefinition
from dateutil.relativedelta import relativedelta
from teamster.core.utils.classes import FiscalYearPartitionsDefinition


def format_oracle_timestamp(timestamp: float, tz: ZoneInfo) -> str:
    return (
        datetime.fromtimestamp(timestamp=timestamp, tz=tz)
        .replace(tzinfo=None)
        .isoformat(timespec="microseconds")
    )


def get_partition_window(partition_key: str, partitions_def) -> tuple[str, str]:
    start = datetime.fromisoformat(partition_key)
    if isinstance(partitions_def, FiscalYearPartitionsDefinition):
        end = (start + relativedelta(years=1) - relativedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
    elif isinstance(partitions_def, MonthlyPartitionsDefinition):
        end = (start + relativedelta(months=1) - relativedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
    else:
        raise TypeError(f"Unsupported partitions_def type: {type(partitions_def)}")
    return (
        start.isoformat(timespec="microseconds"),
        end.isoformat(timespec="microseconds"),
    )
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/libraries/test_powerschool_odbc_utils.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/libraries/test_powerschool_odbc_utils.py src/teamster/libraries/powerschool/sis/odbc/utils.py
git commit -m "feat(powerschool/odbc): add format_oracle_timestamp and get_partition_window"
```

---

### Task 2: `StalenessResult` and `powerschool_connection`

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`

No unit tests for `powerschool_connection` — lifecycle logic requires mocking
subprocess/SSH behavior. `StalenessResult` correctness is verified through
`evaluate_asset_staleness` tests in Tasks 3–4.

- [ ] **Step 1: Add dataclass and context manager to `utils.py`**

New imports to add at the top of `utils.py`:

```python
from contextlib import contextmanager
from dataclasses import dataclass

from dagster import AssetKey
```

Add after `get_partition_window`:

```python
@dataclass
class StalenessResult:
    asset_key: AssetKey
    partitions_def_identifier: str | None
    partition_key: str | None


@contextmanager
def powerschool_connection(ssh_resource, db_resource, log):
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

- [ ] **Step 2: Verify no import errors**

```bash
uv run python -c "from teamster.libraries.powerschool.sis.odbc.utils import StalenessResult, powerschool_connection; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/teamster/libraries/powerschool/sis/odbc/utils.py
git commit -m "feat(powerschool/odbc): add StalenessResult and powerschool_connection"
```

---

### Task 3: Non-partitioned staleness detection

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Modify: `tests/libraries/test_powerschool_odbc_utils.py`

Implements `_evaluate_non_partitioned` and the non-partitioned path in
`evaluate_asset_staleness`. Three test cases: never materialized, modified count
stale, table count mismatch stale.

- [ ] **Step 1: Write failing tests** — add to
      `tests/libraries/test_powerschool_odbc_utils.py`

Helper: `_make_non_partitioned_asset(table_name, partition_column)` builds a
MagicMock asset with `partitions_def = None` and `metadata_by_key` set.

Helper: `_make_event(records, timestamp)` builds a MagicMock materialization
event with `asset_materialization.metadata` containing `records` and
`latest_materialization_timestamp`.

Imports needed: `from dagster import AssetKey, DagsterInstance` and
`from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource`.

Add the following to the test file.

```python
from dagster import AssetKey
from teamster.libraries.powerschool.sis.odbc.utils import (
    evaluate_asset_staleness,
)
```

Add helpers:

```python
def _make_non_partitioned_asset(table_name, partition_column=None):
    asset = MagicMock()
    setattr(asset, "key", AssetKey(table_name))
    asset.partitions_def = None
    asset.metadata_by_key = {
        asset.key: {
            "table_name": MagicMock(value=table_name),
            "partition_column": MagicMock(value=partition_column),
        }
    }
    return asset


def _make_event(records, timestamp):
    event = MagicMock()
    event.asset_materialization.metadata = {
        "records": MagicMock(value=records),
        "latest_materialization_timestamp": MagicMock(value=timestamp),
    }
    return event


def test_non_partitioned_never_materialized():
    asset = _make_non_partitioned_asset("PS_TABLE")
    instance = MagicMock()
    instance.get_latest_materialization_events.return_value = {asset.key: None}
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=MagicMock(),
        log=MagicMock(),
    )
    assert len(results) == 1


def test_non_partitioned_modified_count_stale():
    asset = _make_non_partitioned_asset("PS_TABLE", partition_column="WHENMODIFIED")
    event = _make_event(records=10, timestamp=1700000000.0)
    instance = MagicMock()
    instance.get_latest_materialization_events.return_value = {asset.key: event}
    db = MagicMock()
    db.execute_query.return_value = [(5,)]
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=db,
        log=MagicMock(),
    )
    assert len(results) == 1


def test_non_partitioned_table_count_mismatch_stale():
    asset = _make_non_partitioned_asset("PS_TABLE")
    event = _make_event(records=10, timestamp=1700000000.0)
    instance = MagicMock()
    instance.get_latest_materialization_events.return_value = {asset.key: event}
    db = MagicMock()
    db.execute_query.return_value = [(15,)]
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=db,
        log=MagicMock(),
    )
    assert len(results) == 1


def test_non_partitioned_modified_count_zero_falls_through_to_count_mismatch():
    asset = _make_non_partitioned_asset("PS_TABLE", partition_column="WHENMODIFIED")
    event = _make_event(records=10, timestamp=1700000000.0)
    instance = MagicMock()
    instance.get_latest_materialization_events.return_value = {asset.key: event}
    db = MagicMock()
    db.execute_query.side_effect = [[(0,)], [(15,)]]
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=db,
        log=MagicMock(),
    )
    assert len(results) == 1
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/libraries/test_powerschool_odbc_utils.py -v
```

Expected: ImportError (evaluate_asset_staleness not yet defined)

- [ ] **Step 3: Implement**

Add imports to `src/teamster/libraries/powerschool/sis/odbc/utils.py` (extend
existing dagster import and add new ones):

```python
import oracledb
from dagster import AssetsDefinition, DagsterInstance
from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
```

Add after `powerschool_connection`:

```python
def _evaluate_non_partitioned(
    asset, latest_event, connection, db_powerschool, execution_timezone, log
):
    table_name = asset.metadata_by_key[asset.key]["table_name"].value
    partition_column = asset.metadata_by_key[asset.key]["partition_column"].value

    if latest_event is None:
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    materialization_count = (
        latest_event.asset_materialization.metadata["records"].value
    )
    latest_ts = latest_event.asset_materialization.metadata[
        "latest_materialization_timestamp"
    ].value

    if partition_column is not None:
        query = get_query_text(
            table=table_name,
            column=partition_column,
            start_value=format_oracle_timestamp(latest_ts, execution_timezone),
        )
        [(modified_count,)] = db_powerschool.execute_query(
            connection=connection, query=query, prefetch_rows=2, array_size=1
        )
        if modified_count > 0:
            return StalenessResult(
                asset_key=asset.key,
                partitions_def_identifier=None,
                partition_key=None,
            )

    query = get_query_text(table=table_name, column=None)
    [(table_count,)] = db_powerschool.execute_query(
        connection=connection, query=query, prefetch_rows=2, array_size=1
    )
    if table_count != materialization_count:
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    return None


def evaluate_asset_staleness(
    asset_selection: list[AssetsDefinition],
    execution_timezone: ZoneInfo,
    instance: DagsterInstance,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log,
    limit_monthly_partitions: int | None = None,
) -> list[StalenessResult]:
    non_partitioned = [a for a in asset_selection if a.partitions_def is None]
    results = []

    if non_partitioned:
        non_partitioned_keys = [getattr(a, "key") for a in non_partitioned]
        latest_events = instance.get_latest_materialization_events(
            non_partitioned_keys
        )
        for asset in non_partitioned:
            result = _evaluate_non_partitioned(
                asset=asset,
                latest_event=latest_events.get(asset.key),
                connection=connection,
                db_powerschool=db_powerschool,
                execution_timezone=execution_timezone,
                log=log,
            )
            if result is not None:
                results.append(result)

    return results
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/libraries/test_powerschool_odbc_utils.py -v
```

Expected: 8 PASSED (4 from Task 1 + 4 from Task 3)

- [ ] **Step 5: Commit**

```bash
git add tests/libraries/test_powerschool_odbc_utils.py src/teamster/libraries/powerschool/sis/odbc/utils.py
git commit -m "feat(powerschool/odbc): add evaluate_asset_staleness non-partitioned path"
```

---

### Task 4: Partitioned staleness detection

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/utils.py`
- Modify: `tests/libraries/test_powerschool_odbc_utils.py`

Implements `_evaluate_partition`, `_evaluate_partitioned`, and the partitioned
path in `evaluate_asset_staleness`. Four test cases: skip first partition, never
materialized, last partition modified count stale, and limit_monthly_partitions
slicing.

- [ ] **Step 1: Write failing tests**

Add the following to the test file:

```python
def _make_partitioned_asset(table_name, partitions_def, partition_column="DCID"):
    asset = MagicMock()
    setattr(asset, "key", AssetKey(table_name))
    asset.partitions_def = partitions_def
    asset.metadata_by_key = {
        asset.key: {
            "table_name": MagicMock(value=table_name),
            "partition_column": MagicMock(value=partition_column),
        }
    }
    return asset


def _make_fetch_result(records_count=None, timestamp=None):
    result = MagicMock()
    if records_count is None:
        result.records = []
    else:
        record = MagicMock()
        record.asset_materialization.metadata = {
            "records": MagicMock(value=records_count),
            "latest_materialization_timestamp": MagicMock(value=timestamp),
        }
        result.records = [record]
    return result


def test_partitioned_skips_first_partition():
    partitions_def = MonthlyPartitionsDefinition(
        start_date="2024-01-01", timezone="UTC"
    )
    asset = _make_partitioned_asset("PS_TABLE", partitions_def)
    instance = MagicMock()
    instance.fetch_materializations.return_value = _make_fetch_result()
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=MagicMock(),
        log=MagicMock(),
    )
    first = partitions_def.get_first_partition_key()
    assert all(r.partition_key != first for r in results)


def test_partitioned_never_materialized():
    partitions_def = MonthlyPartitionsDefinition(
        start_date="2024-01-01", timezone="UTC"
    )
    asset = _make_partitioned_asset("PS_TABLE", partitions_def)
    instance = MagicMock()
    instance.fetch_materializations.return_value = _make_fetch_result()
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=MagicMock(),
        log=MagicMock(),
        limit_monthly_partitions=1,
    )
    assert len(results) == 1


def test_partitioned_last_partition_stale():
    partitions_def = MonthlyPartitionsDefinition(
        start_date="2024-01-01", timezone="UTC"
    )
    asset = _make_partitioned_asset("PS_TABLE", partitions_def)
    instance = MagicMock()
    instance.fetch_materializations.return_value = _make_fetch_result(
        records_count=10, timestamp=1700000000.0
    )
    db = MagicMock()
    db.execute_query.return_value = [(5,)]
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=db,
        log=MagicMock(),
        limit_monthly_partitions=1,
    )
    assert len(results) == 1


def test_limit_monthly_partitions():
    partitions_def = MonthlyPartitionsDefinition(
        start_date="2024-01-01", timezone="UTC"
    )
    asset = _make_partitioned_asset("PS_TABLE", partitions_def)
    instance = MagicMock()
    instance.fetch_materializations.return_value = _make_fetch_result()
    evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=MagicMock(),
        log=MagicMock(),
        limit_monthly_partitions=2,
    )
    assert instance.fetch_materializations.call_count == 2


def test_partitioned_window_count_mismatch_stale():
    partitions_def = MonthlyPartitionsDefinition(
        start_date="2024-01-01", timezone="UTC"
    )
    asset = _make_partitioned_asset("PS_TABLE", partitions_def, partition_column="YEARID")
    instance = MagicMock()
    instance.fetch_materializations.return_value = _make_fetch_result(
        records_count=10, timestamp=1700000000.0
    )
    db = MagicMock()
    # First call: window count for second-to-last partition = 15 (≠ 10) → stale
    # Second call: modified count for last partition = 0 → not stale
    db.execute_query.side_effect = [[(15,)], [(0,)]]
    results = evaluate_asset_staleness(
        asset_selection=[asset],
        execution_timezone=ZoneInfo("UTC"),
        instance=instance,
        connection=MagicMock(),
        db_powerschool=db,
        log=MagicMock(),
        limit_monthly_partitions=2,
    )
    assert len(results) == 1
    last = partitions_def.get_last_partition_key()
    assert results[0].partition_key != last
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/libraries/test_powerschool_odbc_utils.py -v
```

Expected: 5 new tests fail (partitioned path not yet implemented)

- [ ] **Step 3: Implement**

Add to the dagster import in
`src/teamster/libraries/powerschool/sis/odbc/utils.py`:

```python
from dagster import AssetRecordsFilter
```

Add after `_evaluate_non_partitioned`:

```python
def _evaluate_partition(
    asset,
    partition_key,
    first_partition_key,
    last_partition_key,
    connection,
    db_powerschool,
    execution_timezone,
    instance,
    log,
):
    if partition_key == first_partition_key:
        return None

    table_name = asset.metadata_by_key[asset.key]["table_name"].value
    partition_column = asset.metadata_by_key[asset.key]["partition_column"].value

    records = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=asset.key,
            asset_partitions=[partition_key],
        ),
        limit=1,
    )
    if not records.records:
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=(
                asset.partitions_def.get_serializable_unique_identifier()
            ),
            partition_key=partition_key,
        )

    event = records.records[0]
    materialization_count = event.asset_materialization.metadata["records"].value
    latest_ts = event.asset_materialization.metadata[
        "latest_materialization_timestamp"
    ].value

    if partition_key == last_partition_key:
        query = get_query_text(
            table=table_name,
            column=partition_column,
            start_value=format_oracle_timestamp(latest_ts, execution_timezone),
        )
        [(modified_count,)] = db_powerschool.execute_query(
            connection=connection, query=query, prefetch_rows=2, array_size=1
        )
        if modified_count > 0:
            return StalenessResult(
                asset_key=asset.key,
                partitions_def_identifier=(
                    asset.partitions_def.get_serializable_unique_identifier()
                ),
                partition_key=partition_key,
            )
        return None

    start_value, end_value = get_partition_window(
        partition_key, asset.partitions_def
    )
    query = get_query_text(
        table=table_name,
        column=partition_column,
        start_value=start_value,
        end_value=end_value,
    )
    [(partition_count,)] = db_powerschool.execute_query(
        connection=connection, query=query, prefetch_rows=2, array_size=1
    )
    if partition_count > 0 and partition_count != materialization_count:
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=(
                asset.partitions_def.get_serializable_unique_identifier()
            ),
            partition_key=partition_key,
        )

    return None


def _evaluate_partitioned(
    asset, partition_keys, connection, db_powerschool,
    execution_timezone, instance, log,
):
    first_partition_key = asset.partitions_def.get_first_partition_key()
    last_partition_key = asset.partitions_def.get_last_partition_key()
    results = []
    for partition_key in partition_keys:
        result = _evaluate_partition(
            asset=asset,
            partition_key=partition_key,
            first_partition_key=first_partition_key,
            last_partition_key=last_partition_key,
            connection=connection,
            db_powerschool=db_powerschool,
            execution_timezone=execution_timezone,
            instance=instance,
            log=log,
        )
        if result is not None:
            results.append(result)
    return results
```

Replace `return results` at the end of `evaluate_asset_staleness` with:

```python
    partitioned = [a for a in asset_selection if a.partitions_def is not None]
    for asset in partitioned:
        partition_keys = asset.partitions_def.get_partition_keys()
        if (
            isinstance(asset.partitions_def, MonthlyPartitionsDefinition)
            and limit_monthly_partitions is not None
        ):
            partition_keys = partition_keys[-limit_monthly_partitions:]
        results.extend(
            _evaluate_partitioned(
                asset=asset,
                partition_keys=partition_keys,
                connection=connection,
                db_powerschool=db_powerschool,
                execution_timezone=execution_timezone,
                instance=instance,
                log=log,
            )
        )

    return results
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/libraries/test_powerschool_odbc_utils.py -v
```

Expected: 13 PASSED (4 + 4 + 5)

- [ ] **Step 5: Commit**

```bash
git add tests/libraries/test_powerschool_odbc_utils.py src/teamster/libraries/powerschool/sis/odbc/utils.py
git commit -m "feat(powerschool/odbc): add evaluate_asset_staleness partitioned path"
```

---

### Task 5: Refactor `assets.py`

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/assets.py`

Replace the inline partition window calculation and SSH lifecycle with the new
utilities. No new tests — behavior is unchanged; the utils tests cover the
extracted logic.

- [ ] **Step 1: Update imports**

Remove from the dagster import block: `MonthlyPartitionsDefinition` Remove
standalone import: `from dateutil.relativedelta import relativedelta` Remove
standalone import:
`from teamster.core.utils.classes import FiscalYearPartitionsDefinition`

Add new import:

```python
from teamster.libraries.powerschool.sis.odbc.utils import (
    get_partition_window,
    powerschool_connection,
)
```

- [ ] **Step 2: Replace partition window calculation**

Replace lines 85–116 in `_asset` (the `partition_start`/`partition_end_fmt`
block) with:

```python
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
```

- [ ] **Step 3: Replace SSH lifecycle**

Replace lines 124–147 in `_asset` (tunnel open through `finally`) with:

```python
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
```

- [ ] **Step 4: Verify no import errors**

```bash
uv run python -c "from teamster.libraries.powerschool.sis.odbc.assets import build_powerschool_table_asset; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add src/teamster/libraries/powerschool/sis/odbc/assets.py
git commit -m "refactor(powerschool/odbc): use get_partition_window and powerschool_connection in assets"
```

---

### Task 6: Refactor `schedules.py`

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/schedules.py`

Replace ~260 lines of inline staleness logic with a call to
`evaluate_asset_staleness`. Target: ~50 lines.

- [ ] **Step 1: Replace the entire file**

```python
from itertools import groupby
from operator import attrgetter
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
            stale = evaluate_asset_staleness(
                asset_selection=asset_selection,
                execution_timezone=execution_timezone,
                instance=context.instance,
                connection=connection,
                db_powerschool=db_powerschool,
                log=context.log,
                limit_monthly_partitions=12,
            )

        item_getter = attrgetter("partitions_def_identifier", "partition_key")

        for (partitions_def_identifier, partition_key), group in groupby(
            iterable=sorted(stale, key=item_getter), key=item_getter
        ):
            yield RunRequest(
                run_key=f"{partitions_def_identifier or ''}_{partition_key or ''}",
                asset_selection=[r.asset_key for r in group],
                partition_key=partition_key,
                tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
            )

    return _schedule
```

- [ ] **Step 2: Verify**

```bash
uv run python -c "from teamster.libraries.powerschool.sis.odbc.schedules import build_powerschool_sis_asset_schedule; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/teamster/libraries/powerschool/sis/odbc/schedules.py
git commit -m "refactor(powerschool/odbc): simplify schedules.py using evaluate_asset_staleness"
```

---

### Task 7: Refactor `sensors.py`

**Files:**

- Modify: `src/teamster/libraries/powerschool/sis/odbc/sensors.py`

Same pattern as Task 6. Target: ~70 lines.

- [ ] **Step 1: Replace the entire file**

```python
from collections import defaultdict
from datetime import datetime
from itertools import groupby
from operator import attrgetter
from zoneinfo import ZoneInfo

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetKey,
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
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
                f"{base_job_name}_"
                f"{partitions_def.get_serializable_unique_identifier()}"
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
    ) -> SensorResult | SkipReason:
        with powerschool_connection(
            ssh_powerschool, db_powerschool, context.log
        ) as connection:
            stale = evaluate_asset_staleness(
                asset_selection=asset_selection,
                execution_timezone=execution_timezone,
                instance=context.instance,
                connection=connection,
                db_powerschool=db_powerschool,
                log=context.log,
            )

        run_requests = []
        item_getter = attrgetter("partitions_def_identifier", "partition_key")

        for (partitions_def_identifier, partition_key), group in groupby(
            iterable=sorted(stale, key=item_getter), key=item_getter
        ):
            job_name = (
                f"{base_job_name}_{partitions_def_identifier}"
                if partitions_def_identifier is not None
                else f"{base_job_name}_None"
            )
            run_requests.append(
                RunRequest(
                    run_key=(
                        f"{job_name}_{partition_key}_{datetime.now().timestamp()}"
                    ),
                    job_name=job_name,
                    partition_key=partition_key,
                    asset_selection=[r.asset_key for r in group],
                    tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                )
            )

        return SensorResult(run_requests=run_requests)

    return _sensor
```

- [ ] **Step 2: Verify**

```bash
uv run python -c "from teamster.libraries.powerschool.sis.odbc.sensors import build_powerschool_asset_sensor; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Run full definition validation**

```bash
uv run pytest tests/test_dagster_definitions.py -v
```

Expected: all definition tests pass

- [ ] **Step 4: Commit**

```bash
git add src/teamster/libraries/powerschool/sis/odbc/sensors.py
git commit -m "refactor(powerschool/odbc): simplify sensors.py using evaluate_asset_staleness"
```

---
