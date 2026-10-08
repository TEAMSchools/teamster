"""Unit tests for the PowerSchool dlt intraday sensor factory (no external deps)."""

import types
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from dagster import build_sensor_context, instance_for_test
from dlt.common.configuration.utils import ResolvedValueTrace, get_resolved_traces

from teamster.libraries.dlt.powerschool import sensors as sensors_module
from teamster.libraries.dlt.powerschool.sensors import (
    _build_run_request,
    build_powerschool_dlt_intraday_sensor,
)
from teamster.libraries.dlt.probe import ProbeTable


def test_sensor_factory_shape():
    sensor_def = build_powerschool_dlt_intraday_sensor(
        code_location="kipppaterson",
        tables=[ProbeTable(name="students", cursor_column="transaction_date")],
        nightly_schedule_name=(
            "kipppaterson__powerschool__dlt__nightly_asset_job_schedule"
        ),
    )

    assert sensor_def.name == "kipppaterson__powerschool__dlt__intraday_sensor"
    assert sensor_def.minimum_interval_seconds == 900
    assert sensor_def.required_resource_keys == {"ssh_powerschool", "db_powerschool"}


def test_build_run_request_selects_changed_and_passes_signatures():
    changed = [
        ProbeTable(name="students", cursor_column="transaction_date"),
        ProbeTable(name="gen", cursor_column=None),
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


class _TracingPipeline:
    """Logs a config-resolution trace on `sync_destination`, as dlt's resolver
    does for every BigQuery config field it looks up."""

    def sync_destination(self) -> None:
        get_resolved_traces().log(
            ResolvedValueTrace(
                key="key",
                value="value",
                default_value=None,
                hint=str,
                sections=(),
                provider_name="test",
                config=None,  # type: ignore[arg-type]
            )
        )


def test_sensor_does_not_accumulate_dlt_config_traces(tmp_path: Path):
    """dlt clears its per-thread trace log only at the end of a traced
    pipeline step, which a sensor tick never runs; each logged trace pins that
    tick's whole pipeline, so without a per-tick clear the long-lived code
    server grows until OOM."""
    url = f"sqlite:///{tmp_path / 'ps.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("create table gen (id integer not null)"))
    engine.dispose()

    tables = [ProbeTable(name="gen", cursor_column=None)]
    sensor_def = build_powerschool_dlt_intraday_sensor(
        code_location="kipppaterson",
        tables=tables,
        nightly_schedule_name=(
            "kipppaterson__powerschool__dlt__nightly_asset_job_schedule"
        ),
    )

    with (
        instance_for_test() as instance,
        build_sensor_context(
            instance=instance,
            sensor_name=sensor_def.name,
            resources={
                "ssh_powerschool": types.SimpleNamespace(open_ssh_tunnel=nullcontext),
                "db_powerschool": types.SimpleNamespace(connection_url=lambda: url),
            },
        ) as context,
    ):
        with (
            patch.object(
                sensors_module,
                "build_powerschool_dlt_pipeline",
                return_value=_TracingPipeline(),
            ),
            patch.object(
                sensors_module,
                "stored_signatures",
                return_value={"gen": {"count": 0, "max_cursor": None}},
            ),
        ):
            for _ in range(3):
                sensor_def(context)

    # the start-of-tick clear leaves only the latest tick's traces
    assert len(get_resolved_traces().all_traces) == 1
