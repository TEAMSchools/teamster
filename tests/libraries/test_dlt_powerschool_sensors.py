"""Unit tests for the PowerSchool dlt intraday sensor factory (no external deps)."""

from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable
from teamster.libraries.dlt.powerschool.sensors import (
    _build_run_request,
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
