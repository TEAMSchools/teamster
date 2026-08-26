"""Unit tests for the Focus dlt intraday sensor factory (no external deps)."""

import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

import sqlalchemy as sa
from dagster import RunRequest, SkipReason, build_sensor_context, instance_for_test
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus import sensors as sensors_module
from teamster.libraries.dlt.focus.sensors import (
    _build_run_request,
    build_focus_dlt_intraday_sensor,
)
from teamster.libraries.dlt.probe import ProbeTable, probe_signature

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
        ProbeTable(name="co_teachers", cursor_column=None),
    ]

    sensor_def = build_focus_dlt_intraday_sensor(
        code_location="kippmiami",
        tables=tables,
        sql_database_credentials=CREDENTIALS,
        nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
    )

    selection: Any = sensor_def.asset_selection

    assert sorted(k.to_user_string() for k in selection.selected_keys) == [
        "kippmiami/dlt/focus/co_teachers",
        "kippmiami/dlt/focus/students",
    ]


def test_build_run_request_selects_changed_and_passes_signatures() -> None:
    changed = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="co_teachers", cursor_column=None),
    ]
    current = {
        "students": {"count": 43, "max_cursor": "2026-08-09T00:00:00"},
        "co_teachers": {"count": 10, "max_cursor": None},
        # unchanged table present in the probe but not in `changed`:
        "districts": {"count": 1, "max_cursor": "2026-07-01T00:00:00"},
    }

    run_request = _build_run_request("kippmiami", changed, current)

    # trunk-ignore(pyright): asset_selection is always set in our RunRequests
    assert [k.to_user_string() for k in run_request.asset_selection] == [
        "kippmiami/dlt/focus/students",
        "kippmiami/dlt/focus/co_teachers",
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
                        "co_teachers": {"count": 10, "max_cursor": None},
                    }
                }
            }
        }
    }
    assert run_request.tags["dagster/max_runtime"] == "3600"


class _FakePipeline:
    """Stand-in for the dlt pipeline the sensor reads baselines from.

    `sync_destination` is a no-op; the baseline itself comes from a patched
    `stored_signatures`, never from this object's `.state`.
    """

    def sync_destination(self) -> None:
        pass


def _seed_sqlite(tmp_path: Path) -> str:
    """A sqlite db standing in for Focus Postgres: one cursor table and one
    no-cursor table, both with deterministic rows so `probe_signature` runs for
    real and produces a predictable signature."""
    url = f"sqlite:///{tmp_path / 'focus.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("create table students (id integer not null, updated_at text)")
        )
        conn.execute(sa.text("insert into students values (1, '2026-08-01T00:00:00')"))
        conn.execute(sa.text("insert into students values (2, '2026-08-02T00:00:00')"))
        conn.execute(sa.text("create table districts (id integer not null)"))
        conn.execute(sa.text("insert into districts values (1)"))
    engine.dispose()
    return url


def _probe_all(url: str, tables: list[ProbeTable]) -> dict[str, dict]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            return {
                table.name: probe_signature(connection, table.name, table.cursor_column)
                for table in tables
            }
    finally:
        engine.dispose()


def _build_sensor(tables: list[ProbeTable], url: str):
    return build_focus_dlt_intraday_sensor(
        code_location="kippmiami",
        tables=tables,
        sql_database_credentials=ConnectionStringCredentials(url),
        nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
    )


def test_sensor_skips_when_run_in_flight(tmp_path: Path) -> None:
    url = _seed_sqlite(tmp_path)
    sensor_def = _build_sensor(
        [ProbeTable(name="students", cursor_column="updated_at")], url
    )

    fake_record = types.SimpleNamespace(
        dagster_run=types.SimpleNamespace(run_id="in-flight-run-id")
    )

    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance, sensor_name=sensor_def.name)

        with (
            patch.object(sensors_module, "in_flight_run", return_value=fake_record),
            patch.object(
                sensors_module, "build_focus_dlt_pipeline", return_value=_FakePipeline()
            ),
        ):
            result = sensor_def(context)

    assert isinstance(result, SkipReason)
    assert result.skip_message is not None
    assert "in-flight-run-id" in result.skip_message


def test_sensor_skips_when_no_drift(tmp_path: Path) -> None:
    url = _seed_sqlite(tmp_path)
    tables = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="districts", cursor_column=None),
    ]
    sensor_def = _build_sensor(tables, url)

    baseline = _probe_all(url, tables)

    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance, sensor_name=sensor_def.name)

        with (
            patch.object(
                sensors_module, "build_focus_dlt_pipeline", return_value=_FakePipeline()
            ),
            patch.object(sensors_module, "stored_signatures", return_value=baseline),
        ):
            result = sensor_def(context)

    assert isinstance(result, SkipReason)


def test_sensor_requests_only_drifted_tables(tmp_path: Path) -> None:
    url = _seed_sqlite(tmp_path)
    tables = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="districts", cursor_column=None),
    ]
    sensor_def = _build_sensor(tables, url)

    current = _probe_all(url, tables)
    # stale baseline for `students` only -- it must drift; `districts` must not.
    baseline = dict(current)
    baseline["students"] = {"count": 1, "max_cursor": "2026-01-01T00:00:00"}

    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance, sensor_name=sensor_def.name)

        with (
            patch.object(
                sensors_module, "build_focus_dlt_pipeline", return_value=_FakePipeline()
            ),
            patch.object(sensors_module, "stored_signatures", return_value=baseline),
        ):
            result = sensor_def(context)

    assert isinstance(result, RunRequest)
    assert result.asset_selection is not None
    assert [k.to_user_string() for k in result.asset_selection] == [
        "kippmiami/dlt/focus/students"
    ]
    assert result.run_config["ops"]["kippmiami__dlt__focus"]["config"]["probe"] == {
        "students": current["students"]
    }
