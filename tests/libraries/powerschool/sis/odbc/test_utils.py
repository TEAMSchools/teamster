"""Unit tests for PowerSchool SIS ODBC utilities."""

from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from dagster import AssetKey, AssetsDefinition, MonthlyPartitionsDefinition

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.odbc.utils import (
    StalenessResult,
    evaluate_asset_staleness,
    format_oracle_timestamp,
    get_partition_window,
    get_query_text,
    powerschool_connection,
)


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
                pass

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


# ---------------------------------------------------------------------------
# Helpers for staleness evaluation tests
# ---------------------------------------------------------------------------


def _make_asset(key, table_name, partition_column=None, partitions_def=None):
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


def _make_materialization_event(records, timestamp):
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


class TestEvaluateAssetStalenessNonPartitioned:
    def _run(self, assets, latest_events, execute_query_rv=None):
        """Shared runner for non-partitioned staleness tests."""
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = latest_events
        connection = MagicMock()
        db = MagicMock()
        if execute_query_rv is not None:
            db.execute_query.return_value = execute_query_rv
        log = MagicMock()
        return evaluate_asset_staleness(
            asset_selection=assets,
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
        )

    def test_never_materialized(self):
        asset = _make_asset("t1", "TABLE1")
        results = self._run([asset], {asset.key: None})
        assert len(results) == 1
        assert results[0] == StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    def test_modified_count_gt_zero(self):
        asset = _make_asset("t1", "TABLE1", partition_column="WHENMODIFIED")
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        results = self._run([asset], {asset.key: event}, execute_query_rv=[(5,)])
        assert len(results) == 1
        assert results[0].asset_key == asset.key
        assert results[0].partition_key is None

    def test_table_count_mismatch(self):
        asset = _make_asset("t1", "TABLE1", partition_column=None)
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        results = self._run([asset], {asset.key: event}, execute_query_rv=[(200,)])
        assert len(results) == 1
        assert results[0].asset_key == asset.key

    def test_not_stale(self):
        asset = _make_asset("t1", "TABLE1", partition_column=None)
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        results = self._run([asset], {asset.key: event}, execute_query_rv=[(100,)])
        assert results == []

    def test_modified_count_zero_falls_through_to_table_count(self):
        asset = _make_asset("t1", "TABLE1", partition_column="WHENMODIFIED")
        event = _make_materialization_event(records=100, timestamp=1719835200.0)
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {asset.key: event}
        connection = MagicMock()
        db = MagicMock()
        # First call: modified_count=0, second call: table_count=200
        db.execute_query.side_effect = [[(0,)], [(200,)]]
        log = MagicMock()
        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
        )
        assert len(results) == 1
        assert results[0].asset_key == asset.key
        assert db.execute_query.call_count == 2


class TestEvaluateAssetStalenessPartitioned:
    def _make_partitions_def(self):
        """Create a MonthlyPartitionsDefinition with 3 partition keys."""
        return MonthlyPartitionsDefinition(
            start_date="2024-01-01", end_date="2024-04-01"
        )

    def test_never_materialized_partition(self):
        pdef = self._make_partitions_def()
        asset = _make_asset(
            "t1", "TABLE1", partition_column="WHENMODIFIED", partitions_def=pdef
        )
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {}
        # first partition skipped; second + third have no records
        instance.fetch_materializations.return_value = _make_event_records([])
        connection = MagicMock()
        db = MagicMock()
        log = MagicMock()
        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
        )
        # 2024-02-01 and 2024-03-01 should be stale (first partition skipped)
        assert len(results) == 2
        keys = [r.partition_key for r in results]
        assert "2024-02-01" in keys
        assert "2024-03-01" in keys
        assert results[0].partitions_def_identifier is not None

    def test_skip_first_partition(self):
        pdef = self._make_partitions_def()
        asset = _make_asset(
            "t1", "TABLE1", partition_column="WHENMODIFIED", partitions_def=pdef
        )
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {}
        # All partitions return records so they are materialized
        mat_event = MagicMock()
        mat_event.asset_materialization = MagicMock()
        mat_event.asset_materialization.metadata = {
            "records": MagicMock(value=10),
            "latest_materialization_timestamp": MagicMock(value=1719835200.0),
        }
        instance.fetch_materializations.return_value = _make_event_records([mat_event])
        connection = MagicMock()
        db = MagicMock()
        # For last partition: modified_count=0; for mid partitions: partition_count matches
        db.execute_query.return_value = [(10,)]
        log = MagicMock()
        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
        )
        # First partition (2024-01-01) should never appear in results
        first_pk = "2024-01-01"
        assert all(r.partition_key != first_pk for r in results)

    def test_last_partition_modified_count_gt_zero(self):
        pdef = self._make_partitions_def()
        asset = _make_asset(
            "t1", "TABLE1", partition_column="WHENMODIFIED", partitions_def=pdef
        )
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {}
        mat_event = MagicMock()
        mat_event.asset_materialization = MagicMock()
        mat_event.asset_materialization.metadata = {
            "records": MagicMock(value=10),
            "latest_materialization_timestamp": MagicMock(value=1719835200.0),
        }
        instance.fetch_materializations.return_value = _make_event_records([mat_event])
        connection = MagicMock()
        db = MagicMock()

        # mid partitions: partition_count matches (10); last partition: modified=5
        def query_side_effect(**kwargs):
            query_str = str(kwargs.get("query", ""))
            if "BETWEEN" in query_str:
                return [(10,)]
            return [(5,)]

        db.execute_query.side_effect = query_side_effect
        log = MagicMock()
        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
        )
        last_pk = "2024-03-01"
        assert any(r.partition_key == last_pk for r in results)

    def test_partition_count_mismatch(self):
        pdef = self._make_partitions_def()
        asset = _make_asset(
            "t1", "TABLE1", partition_column="WHENMODIFIED", partitions_def=pdef
        )
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {}
        mat_event = MagicMock()
        mat_event.asset_materialization = MagicMock()
        mat_event.asset_materialization.metadata = {
            "records": MagicMock(value=10),
            "latest_materialization_timestamp": MagicMock(value=1719835200.0),
        }
        instance.fetch_materializations.return_value = _make_event_records([mat_event])
        connection = MagicMock()
        db = MagicMock()
        # All queries return partition_count=20, but materialization records=10
        db.execute_query.return_value = [(20,)]
        log = MagicMock()
        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
        )
        # Mid partition (2024-02-01) should be stale due to count mismatch
        mid_pk = "2024-02-01"
        assert any(r.partition_key == mid_pk for r in results)

    def test_limit_monthly_partitions_slicing(self):
        pdef = self._make_partitions_def()
        asset = _make_asset(
            "t1", "TABLE1", partition_column="WHENMODIFIED", partitions_def=pdef
        )
        instance = MagicMock()
        instance.get_latest_materialization_events.return_value = {}
        # All partitions unmaterialized
        instance.fetch_materializations.return_value = _make_event_records([])
        connection = MagicMock()
        db = MagicMock()
        log = MagicMock()
        results = evaluate_asset_staleness(
            asset_selection=[asset],
            execution_timezone=ZoneInfo("UTC"),
            instance=instance,
            connection=connection,
            db_powerschool=db,
            log=log,
            limit_monthly_partitions=1,
        )
        # Only last 1 partition key checked; first_partition skip still applies
        # With limit=1, only 2024-03-01 is checked, and it's not the first
        assert len(results) == 1
        assert results[0].partition_key == "2024-03-01"
