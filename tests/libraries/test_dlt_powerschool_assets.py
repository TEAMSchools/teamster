"""Unit tests for the probe-gated PowerSchool dlt factory (no external deps)."""

from datetime import datetime

from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolTable,
    probe_signature,
)


class FakeResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def execute(self, clause):
        self.queries.append(str(clause))
        return FakeResult(self.row)


def test_probe_signature_shapes_datetime_cursor():
    conn = FakeConnection((42, datetime(2026, 7, 15, 13, 30, 0)))

    sig = probe_signature(conn, "students", "transaction_date")

    assert sig == {"count": 42, "max_cursor": "2026-07-15T13:30:00"}
    assert "COUNT(*)" in conn.queries[0]
    assert "MAX(transaction_date)" in conn.queries[0]
    assert "FROM students" in conn.queries[0]


def test_probe_signature_empty_table_none_cursor():
    conn = FakeConnection((0, None))

    sig = probe_signature(conn, "cc", "transaction_date")

    assert sig == {"count": 0, "max_cursor": None}


def test_powerschool_table_dataclass():
    t = PowerSchoolTable(name="students", cursor_column="transaction_date")
    n = PowerSchoolTable(name="test", cursor_column=None)

    assert t.cursor_column == "transaction_date"
    assert n.cursor_column is None
