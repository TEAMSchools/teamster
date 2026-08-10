"""Unit tests for the Focus dlt intraday sensor factory (no external deps)."""

from typing import Any

from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.sensors import (
    _build_run_request,
    build_focus_dlt_intraday_sensor,
)
from teamster.libraries.dlt.probe import ProbeTable

CREDENTIALS = ConnectionStringCredentials("postgresql+psycopg://localhost:5432/focus")


def test_sensor_factory_shape() -> None:
    sensor_def = build_focus_dlt_intraday_sensor(
        code_location="kippmiami",
        tables=[ProbeTable(name="students", cursor_column="updated_at")],
        sql_database_credentials=CREDENTIALS,
        nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
    )

    assert sensor_def.name == "kippmiami__dlt__focus__intraday_sensor"
    assert sensor_def.minimum_interval_seconds == 900
    # credentials are closure-captured, not a Dagster resource
    assert sensor_def.required_resource_keys == set()


def test_sensor_selects_every_configured_table() -> None:
    tables = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="login_history", cursor_column=None),
    ]

    sensor_def = build_focus_dlt_intraday_sensor(
        code_location="kippmiami",
        tables=tables,
        sql_database_credentials=CREDENTIALS,
        nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
    )

    selection: Any = sensor_def.asset_selection

    assert sorted(k.to_user_string() for k in selection.selected_keys) == [
        "kippmiami/dlt/focus/login_history",
        "kippmiami/dlt/focus/students",
    ]


def test_build_run_request_selects_changed_and_passes_signatures() -> None:
    changed = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="login_history", cursor_column=None),
    ]
    current = {
        "students": {"count": 43, "max_cursor": "2026-08-09T00:00:00"},
        "login_history": {"count": 10, "max_cursor": None},
        # unchanged table present in the probe but not in `changed`:
        "districts": {"count": 1, "max_cursor": "2026-07-01T00:00:00"},
    }

    run_request = _build_run_request("kippmiami", changed, current)

    # trunk-ignore(pyright): asset_selection is always set in our RunRequests
    assert [k.to_user_string() for k in run_request.asset_selection] == [
        "kippmiami/dlt/focus/students",
        "kippmiami/dlt/focus/login_history",
    ]
    assert run_request.run_config == {
        "ops": {
            "kippmiami__dlt__focus": {
                "config": {
                    "probe": {
                        "students": {
                            "count": 43,
                            "max_cursor": "2026-08-09T00:00:00",
                        },
                        "login_history": {"count": 10, "max_cursor": None},
                    }
                }
            }
        }
    }
    assert run_request.tags["dagster/max_runtime"] == "3600"
