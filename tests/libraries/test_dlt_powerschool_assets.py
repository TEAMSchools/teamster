"""Unit tests for the probe-gated PowerSchool dlt factory (no external deps)."""

import yaml
from dagster import AssetKey

from teamster.libraries.dlt.powerschool.assets import build_powerschool_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable


def _config_entries():
    # The code location already owns this path and derives it from __file__, so
    # it resolves regardless of pytest's cwd. Imported inside the function: a
    # module-scope code-location import needs the dbt manifest at collection.
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    return yaml.safe_load(config_file.read_text())["assets"]


def test_factory_builds_single_subsettable_multiasset():
    tables = [
        ProbeTable(name="students", cursor_column="transaction_date"),
        ProbeTable(name="users", cursor_column="whenmodified"),
        ProbeTable(name="test", cursor_column=None),
    ]

    assets_def = build_powerschool_dlt_assets(
        code_location="kipppaterson", tables=tables
    )

    assert {k.to_user_string() for k in assets_def.keys} == {
        "kipppaterson/powerschool/sis/students",
        "kipppaterson/powerschool/sis/users",
        "kipppaterson/powerschool/sis/test",
    }
    assert assets_def.can_subset is True
    assert assets_def.op.name == "kipppaterson__powerschool"
    assert assets_def.op.pool == "dlt_powerschool_kipppaterson"


def test_assets_module_covers_every_configured_table():
    """ONE multi-asset def whose keys are exactly the configured tables."""
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import assets

    assert len(assets) == 1
    assert {key for a in assets for key in a.keys} == {
        AssetKey(["kipppaterson", "powerschool", "sis", e["table_name"]])
        for e in _config_entries()
    }


def test_triggers_cover_every_table():
    """Every configured table belongs to at least one trigger.

    A table with both membership flags false would silently never materialize
    (the dlt assets carry no automation condition). The overlap between tiers
    must be exactly the no-cursor set: count-gated intraday, authoritative
    overnight.
    """
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        _nightly_targets,
    )

    entries = _config_entries()

    def key(name):
        return f"kipppaterson/powerschool/sis/{name}"

    expected = {key(e["table_name"]) for e in entries}
    intraday = {key(e["table_name"]) for e in entries if e["intraday"]}
    no_cursor = {key(e["table_name"]) for e in entries if e["cursor_column"] is None}

    # Resolve nightly targets through the real scheduling function — the exact
    # code an orphaned membership would route around.
    nightly = set(_nightly_targets())

    assert intraday | nightly == expected
    assert intraday & nightly == no_cursor


def test_nightly_schedule_and_intraday_sensor():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        powerschool_dlt_nightly_asset_job_schedule as nightly,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        schedules,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.sensors import (
        sensors,
    )

    assert schedules == [nightly]
    assert nightly.cron_schedule == "0 2 * * *"
    assert nightly.tags == {"dagster/max_runtime": "3600"}

    (sensor,) = sensors
    assert sensor.name == "kipppaterson__powerschool__dlt__intraday_sensor"
    assert sensor.minimum_interval_seconds == 900


def _resolved_probe_job(tables):
    from dagster import Definitions, define_asset_job
    from dagster_dlt import DagsterDltResource

    from teamster.libraries.dlt.powerschool.resources import OracleResource
    from teamster.libraries.ssh.resources import SSHResource

    assets_def = build_powerschool_dlt_assets(
        code_location="kipppaterson", tables=tables
    )
    defs = Definitions(
        assets=[assets_def],
        jobs=[define_asset_job("probe_job", selection=list(assets_def.keys))],
        resources={
            "dlt": DagsterDltResource(),
            "ssh_powerschool": SSHResource(remote_host="localhost"),
            "db_powerschool": OracleResource(
                user="u", password="p", host="localhost", port="1521", service_name="s"
            ),
        },
    )
    return defs.resolve_job_def("probe_job")


def test_run_config_schema_accepts_probe_payload():
    job = _resolved_probe_job(
        [
            ProbeTable(name="students", cursor_column="transaction_date"),
            ProbeTable(name="gen", cursor_column=None),
        ]
    )

    from dagster import validate_run_config

    validated = validate_run_config(
        job,
        {
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
        },
    )

    assert validated


def test_run_config_schema_accepts_empty_full_refresh():
    job = _resolved_probe_job(
        [ProbeTable(name="students", cursor_column="transaction_date")]
    )

    from dagster import validate_run_config

    assert validate_run_config(job, {})
