"""Unit tests for the PowerSchool dlt intraday sensor factory (no external deps)."""

import types

from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable
from teamster.libraries.dlt.powerschool.sensors import (
    _IN_FLIGHT_STATUSES,
    _build_run_request,
    _in_flight_run,
    build_powerschool_dlt_intraday_sensor,
)


def test_sensor_factory_shape():
    sensor_def = build_powerschool_dlt_intraday_sensor(
        code_location="kipppaterson",
        tables=[PowerSchoolTable(name="students", cursor_column="transaction_date")],
        nightly_schedule_name=(
            "kipppaterson__powerschool__dlt__nightly_asset_job_schedule"
        ),
    )

    assert sensor_def.name == "kipppaterson__powerschool__dlt__intraday_sensor"
    assert sensor_def.minimum_interval_seconds == 900
    assert sensor_def.required_resource_keys == {"ssh_powerschool", "db_powerschool"}


def test_build_run_request_selects_changed_and_passes_signatures():
    changed = [
        PowerSchoolTable(name="students", cursor_column="transaction_date"),
        PowerSchoolTable(name="gen", cursor_column=None),
    ]
    current = {
        "students": {"count": 43, "max_cursor": "2026-07-16T00:00:00"},
        "gen": {"count": 10, "max_cursor": None},
        # unchanged table present in the probe but not in `changed`:
        "users": {"count": 1, "max_cursor": "2026-07-01T00:00:00"},
    }

    run_request = _build_run_request("kipppaterson", changed, current)

    # trunk-ignore(pyright): asset_selection is always set in our RunRequests
    assert [k.to_user_string() for k in run_request.asset_selection] == [
        "kipppaterson/powerschool/sis/students",
        "kipppaterson/powerschool/sis/gen",
    ]
    assert run_request.run_config == {
        "ops": {
            "kipppaterson__powerschool": {
                "config": {
                    "probe": {
                        "students": {
                            "count": 43,
                            "max_cursor": "2026-07-16T00:00:00",
                        },
                        "gen": {"count": 10, "max_cursor": None},
                    }
                }
            }
        }
    }
    assert run_request.tags["dagster/max_runtime"] == "3600"


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

    result = _in_flight_run(instance, "the_sensor", "the_nightly_schedule")

    assert result is rec
    # short-circuits on the sensor tag before querying the schedule tag
    assert instance.queried_values == ["the_sensor"]
    assert instance.seen_statuses == _IN_FLIGHT_STATUSES


def test_in_flight_run_returns_schedule_run_when_only_schedule_live():
    rec = _fake_record("nightly-run")
    instance = _FakeInstance({"the_nightly_schedule": [rec]})

    result = _in_flight_run(instance, "the_sensor", "the_nightly_schedule")

    assert result is rec
    # sensor tag queried first (empty), then the schedule tag
    assert instance.queried_values == ["the_sensor", "the_nightly_schedule"]


def test_in_flight_run_none_when_neither_live():
    instance = _FakeInstance({})

    result = _in_flight_run(instance, "the_sensor", "the_nightly_schedule")

    assert result is None
    assert instance.queried_values == ["the_sensor", "the_nightly_schedule"]
