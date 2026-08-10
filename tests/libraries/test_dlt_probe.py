"""Unit tests for the shared dlt probe/gate primitives (no external deps)."""

import types
from datetime import datetime

from teamster.libraries.dlt.probe import (
    IN_FLIGHT_STATUSES,
    ProbeTable,
    compute_changed,
    in_flight_run,
    probe_signature,
    stored_signatures,
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


def test_probe_signature_non_datetime_cursor_stringified():
    # Guard for the ODBC-district template: a future table with a numeric or
    # string change column has no .isoformat(); it must stringify, not raise.
    conn = FakeConnection((7, 12345))

    sig = probe_signature(conn, "some_table", "numeric_cursor")

    assert sig == {"count": 7, "max_cursor": "12345"}


def test_probe_signature_no_cursor_count_only():
    # No-cursor tables are count-gated: COUNT(*) only, and the signature keeps
    # the max_cursor key (None) so it compares equal to the run-config
    # round-trip shape.
    conn = FakeConnection((42,))

    sig = probe_signature(conn, "gen", None)

    assert sig == {"count": 42, "max_cursor": None}
    assert "COUNT(*)" in conn.queries[0]
    assert "MAX(" not in conn.queries[0]


def test_probe_table_dataclass():
    t = ProbeTable(name="students", cursor_column="transaction_date")
    n = ProbeTable(name="test", cursor_column=None)

    assert t.cursor_column == "transaction_date"
    assert n.cursor_column is None


def test_compute_changed_no_cursor_count_drift_included():
    table = ProbeTable(name="gen", cursor_column=None)
    current = {"gen": {"count": 43, "max_cursor": None}}
    stored = {"gen": {"count": 42, "max_cursor": None}}

    changed = compute_changed([table], current, stored)

    assert changed == [table]


def test_compute_changed_no_cursor_stable_count_excluded():
    table = ProbeTable(name="gen", cursor_column=None)
    signature = {"count": 42, "max_cursor": None}
    current = {"gen": dict(signature)}
    stored = {"gen": dict(signature)}

    changed = compute_changed([table], current, stored)

    assert changed == []


def test_compute_changed_no_stored_baseline_included():
    # Bootstrap: a table new to intraday (or first tick ever) has no stored
    # signature and must load once to establish one.
    table = ProbeTable(name="gen", cursor_column=None)
    current = {"gen": {"count": 42, "max_cursor": None}}

    changed = compute_changed([table], current, stored={})

    assert changed == [table]


def test_compute_changed_cursor_table_drift_included():
    table = ProbeTable(name="students", cursor_column="transaction_date")
    current = {"students": {"count": 43, "max_cursor": "2026-07-16T00:00:00"}}
    stored = {"students": {"count": 42, "max_cursor": "2026-07-15T00:00:00"}}

    changed = compute_changed([table], current, stored)

    assert changed == [table]


def test_compute_changed_cursor_table_unchanged_excluded():
    table = ProbeTable(name="students", cursor_column="transaction_date")
    signature = {"count": 42, "max_cursor": "2026-07-15T00:00:00"}
    current = {"students": dict(signature)}
    stored = {"students": dict(signature)}

    changed = compute_changed([table], current, stored)

    assert changed == []


def test_compute_changed_first_run_empty_stored_all_cursor_tables_changed():
    tables = [
        ProbeTable(name="students", cursor_column="transaction_date"),
        ProbeTable(name="users", cursor_column="whenmodified"),
    ]
    current = {
        "students": {"count": 10, "max_cursor": "2026-07-15T00:00:00"},
        "users": {"count": 5, "max_cursor": "2026-07-14T00:00:00"},
    }

    changed = compute_changed(tables, current, stored={})

    assert changed == tables


def test_compute_changed_mixed_set_order_preserved():
    no_cursor = ProbeTable(name="test", cursor_column=None)
    drifted = ProbeTable(name="students", cursor_column="transaction_date")
    unchanged = ProbeTable(name="users", cursor_column="whenmodified")
    selected = [no_cursor, drifted, unchanged]

    unchanged_signature = {"count": 5, "max_cursor": "2026-07-14T00:00:00"}
    current = {
        "test": {"count": 9, "max_cursor": None},
        "students": {"count": 43, "max_cursor": "2026-07-16T00:00:00"},
        "users": dict(unchanged_signature),
    }
    stored = {
        "test": {"count": 8, "max_cursor": None},
        "students": {"count": 42, "max_cursor": "2026-07-15T00:00:00"},
        "users": dict(unchanged_signature),
    }

    changed = compute_changed(selected, current, stored)

    assert changed == [no_cursor, drifted]


def test_stored_signatures_returns_resource_signatures():
    pipeline = types.SimpleNamespace(
        state={
            "sources": {
                "powerschool": {
                    "resources": {
                        "students": {
                            "signature": {
                                "count": 5,
                                "max_cursor": "2026-07-15T00:00:00",
                            }
                        }
                    }
                }
            }
        }
    )

    stored = stored_signatures(pipeline, "powerschool")

    assert stored == {"students": {"count": 5, "max_cursor": "2026-07-15T00:00:00"}}


def test_stored_signatures_first_run_empty_state():
    pipeline = types.SimpleNamespace(state={})

    stored = stored_signatures(pipeline, "powerschool")

    assert stored == {}


class _FakeInstance:
    """Minimal stand-in for DagsterInstance.get_run_records for the in-flight
    guard test: returns canned records keyed by the single tag value in the
    filter, and records each query's tag value + status set."""

    def __init__(self, records_by_value):
        self._by_value = records_by_value
        self.queried_values = []
        self.seen_statuses = None

    def get_run_records(self, filters, limit):
        (value,) = filters.tags.values()
        self.queried_values.append(value)
        self.seen_statuses = filters.statuses
        return self._by_value.get(value, [])


def _fake_record(run_id):
    return types.SimpleNamespace(dagster_run=types.SimpleNamespace(run_id=run_id))


def test_in_flight_run_returns_sensor_run_and_checks_status_set():
    rec = _fake_record("sensor-run")
    instance = _FakeInstance({"the_sensor": [rec]})

    result = in_flight_run(instance, "the_sensor", "the_nightly_schedule")

    assert result is rec
    # short-circuits on the sensor tag before querying the schedule tag
    assert instance.queried_values == ["the_sensor"]
    assert instance.seen_statuses == IN_FLIGHT_STATUSES


def test_in_flight_run_returns_schedule_run_when_only_schedule_live():
    rec = _fake_record("nightly-run")
    instance = _FakeInstance({"the_nightly_schedule": [rec]})

    result = in_flight_run(instance, "the_sensor", "the_nightly_schedule")

    assert result is rec
    # sensor tag queried first (empty), then the schedule tag
    assert instance.queried_values == ["the_sensor", "the_nightly_schedule"]


def test_in_flight_run_none_when_neither_live():
    instance = _FakeInstance({})

    result = in_flight_run(instance, "the_sensor", "the_nightly_schedule")

    assert result is None
    assert instance.queried_values == ["the_sensor", "the_nightly_schedule"]
