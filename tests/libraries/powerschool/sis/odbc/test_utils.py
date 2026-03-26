"""Unit tests for PowerSchool SIS ODBC utilities."""

from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from dagster import MonthlyPartitionsDefinition

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.odbc.utils import (
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
