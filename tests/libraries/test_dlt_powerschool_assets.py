"""Unit tests for the probe-gated PowerSchool dlt factory (no external deps)."""

import pathlib

import yaml

from teamster.libraries.dlt.powerschool.assets import build_powerschool_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable


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


CONFIG = pathlib.Path(
    "src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml"
)

INTRADAY_TRANSACTION_DATE = {
    "attendance",
    "storedgrades",
    "pgfinalgrades",
    "cc",
    "students",
    "courses",
    "schools",
    "sections",
    "termbins",
    "terms",
    # moved off whenmodified in afbd8239b (#4754): these three carry both
    # columns, and an in-place UPDATE that leaves whenmodified alone is
    # invisible to the probe's COUNT(*) + MAX(cursor_column) signature.
    "schoolstaff",
    "sectionteacher",
    "users",
}
INTRADAY_WHENMODIFIED = {
    "gradescaleitem",
    "roledef",
    "s_nj_crs_x",
    "s_nj_ren_x",
    "s_nj_stu_x",
    "s_stu_x",
    "studentcorefields",
    "studentrace",
    "u_expectations",
    "u_studentsuserfields",
    "userscorefields",
}
NIGHTLY_WHENMODIFIED = {
    "assignmentcategoryassoc",
    "assignmentscore",
    "assignmentsection",
    "districtteachercategory",
    "gradecalcformulaweight",
    "gradecalcschoolassoc",
    "gradecalculationtype",
    "gradeformulaset",
    "gradeschoolconfig",
    "gradeschoolformulaassoc",
    "teachercategory",
}
NIGHTLY_NO_CURSOR = {
    "attendance_code",
    "attendance_conversion_items",
    "bell_schedule",
    "calendar_day",
    "cycle_day",
    "fte",
    "gen",
    "log",
    "reenrollments",
    "spenrollments",
    "studenttest",
    "studenttestscore",
    "test",
    "testscore",
}


def test_config_matches_spec_membership_map():
    entries = yaml.safe_load(CONFIG.read_text())["assets"]
    by_name = {e["table_name"]: e for e in entries}

    # derived, not a fourth hand-maintained literal: a table added to the YAML
    # but not to a spec set fails here instead of drifting silently
    assert len(entries) == len(
        INTRADAY_TRANSACTION_DATE
        | INTRADAY_WHENMODIFIED
        | NIGHTLY_WHENMODIFIED
        | NIGHTLY_NO_CURSOR
    )

    for name in INTRADAY_TRANSACTION_DATE:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "transaction_date",
            "intraday": True,
            "nightly": False,
        }
    for name in INTRADAY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "intraday": True,
            "nightly": False,
        }
    for name in NIGHTLY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "intraday": False,
            "nightly": True,
        }
    for name in NIGHTLY_NO_CURSOR:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": None,
            "intraday": True,
            "nightly": True,
        }


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
    assert sensors[0].name == "kipppaterson__powerschool__dlt__intraday_sensor"
    assert sensors[0].minimum_interval_seconds == 900


def test_assets_module_exposes_single_def():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        assets,
    )

    assert len(assets) == 1
    assert len(list(assets[0].keys)) == 49


def test_nightly_targets_sis_keys_and_counts():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        _nightly_targets,
    )

    nightly = _nightly_targets()

    assert len(nightly) == 25
    assert all(t.startswith("kipppaterson/powerschool/sis/") for t in nightly)
    assert "kipppaterson/powerschool/sis/teachercategory" in nightly
    assert "kipppaterson/powerschool/sis/test" in nightly
    assert "kipppaterson/powerschool/sis/students" not in nightly


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
