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
