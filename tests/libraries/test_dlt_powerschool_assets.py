"""Unit tests for the probe-gated PowerSchool dlt factory (no external deps)."""

import pathlib
import types
from datetime import datetime

import yaml

from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolTable,
    _compute_changed,
    _stored_signatures,
    build_powerschool_dlt_assets,
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


def test_powerschool_table_dataclass():
    t = PowerSchoolTable(name="students", cursor_column="transaction_date")
    n = PowerSchoolTable(name="test", cursor_column=None)

    assert t.cursor_column == "transaction_date"
    assert n.cursor_column is None


def test_factory_builds_single_subsettable_multiasset():
    tables = [
        PowerSchoolTable(name="students", cursor_column="transaction_date"),
        PowerSchoolTable(name="users", cursor_column="whenmodified"),
        PowerSchoolTable(name="test", cursor_column=None),
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
}
INTRADAY_WHENMODIFIED = {
    "gradescaleitem",
    "roledef",
    "s_nj_crs_x",
    "s_nj_ren_x",
    "s_nj_stu_x",
    "s_stu_x",
    "schoolstaff",
    "sectionteacher",
    "studentcorefields",
    "studentrace",
    "u_studentsuserfields",
    "users",
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


def test_config_matches_spec_cursor_map():
    entries = yaml.safe_load(CONFIG.read_text())["assets"]
    by_name = {e["table_name"]: e for e in entries}

    assert len(entries) == 48

    for name in INTRADAY_TRANSACTION_DATE:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "transaction_date",
            "schedule_tier": "intraday",
        }
    for name in INTRADAY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "schedule_tier": "intraday",
        }
    for name in NIGHTLY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "schedule_tier": "nightly",
        }
    for name in NIGHTLY_NO_CURSOR:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": None,
            "schedule_tier": "nightly",
        }


def test_schedules_subset_by_tier():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        powerschool_dlt_intraday_asset_job_schedule as intraday,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        powerschool_dlt_nightly_asset_job_schedule as nightly,
    )

    assert intraday.cron_schedule == "*/15 * * * *"
    assert nightly.cron_schedule == "0 2 * * *"
    assert intraday.tags == {"dagster/max_runtime": "3600"}
    assert nightly.tags == {"dagster/max_runtime": "3600"}


def test_assets_module_exposes_single_def():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        assets,
    )

    assert len(assets) == 1
    assert len(list(assets[0].keys)) == 48


def test_tier_targets_sis_keys_and_counts():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        _tier_targets,
    )

    intraday = _tier_targets("intraday")
    nightly = _tier_targets("nightly")

    assert len(intraday) == 23
    assert len(nightly) == 25
    assert all(
        t.startswith("kipppaterson/powerschool/sis/") for t in intraday + nightly
    )
    assert "kipppaterson/powerschool/sis/students" in intraday
    assert "kipppaterson/powerschool/sis/teachercategory" in nightly


def test_compute_changed_no_cursor_count_drift_included():
    table = PowerSchoolTable(name="gen", cursor_column=None)
    current = {"gen": {"count": 43, "max_cursor": None}}
    stored = {"gen": {"count": 42, "max_cursor": None}}

    changed = _compute_changed([table], current, stored)

    assert changed == [table]


def test_compute_changed_no_cursor_stable_count_excluded():
    table = PowerSchoolTable(name="gen", cursor_column=None)
    signature = {"count": 42, "max_cursor": None}
    current = {"gen": dict(signature)}
    stored = {"gen": dict(signature)}

    changed = _compute_changed([table], current, stored)

    assert changed == []


def test_compute_changed_no_stored_baseline_included():
    # Bootstrap: a table new to intraday (or first tick ever) has no stored
    # signature and must load once to establish one.
    table = PowerSchoolTable(name="gen", cursor_column=None)
    current = {"gen": {"count": 42, "max_cursor": None}}

    changed = _compute_changed([table], current, stored={})

    assert changed == [table]


def test_compute_changed_cursor_table_drift_included():
    table = PowerSchoolTable(name="students", cursor_column="transaction_date")
    current = {"students": {"count": 43, "max_cursor": "2026-07-16T00:00:00"}}
    stored = {"students": {"count": 42, "max_cursor": "2026-07-15T00:00:00"}}

    changed = _compute_changed([table], current, stored)

    assert changed == [table]


def test_compute_changed_cursor_table_unchanged_excluded():
    table = PowerSchoolTable(name="students", cursor_column="transaction_date")
    signature = {"count": 42, "max_cursor": "2026-07-15T00:00:00"}
    current = {"students": dict(signature)}
    stored = {"students": dict(signature)}

    changed = _compute_changed([table], current, stored)

    assert changed == []


def test_compute_changed_first_run_empty_stored_all_cursor_tables_changed():
    tables = [
        PowerSchoolTable(name="students", cursor_column="transaction_date"),
        PowerSchoolTable(name="users", cursor_column="whenmodified"),
    ]
    current = {
        "students": {"count": 10, "max_cursor": "2026-07-15T00:00:00"},
        "users": {"count": 5, "max_cursor": "2026-07-14T00:00:00"},
    }

    changed = _compute_changed(tables, current, stored={})

    assert changed == tables


def test_compute_changed_mixed_set_order_preserved():
    no_cursor = PowerSchoolTable(name="test", cursor_column=None)
    drifted = PowerSchoolTable(name="students", cursor_column="transaction_date")
    unchanged = PowerSchoolTable(name="users", cursor_column="whenmodified")
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

    changed = _compute_changed(selected, current, stored)

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

    stored = _stored_signatures(pipeline, "powerschool")

    assert stored == {"students": {"count": 5, "max_cursor": "2026-07-15T00:00:00"}}


def test_stored_signatures_first_run_empty_state():
    pipeline = types.SimpleNamespace(state={})

    stored = _stored_signatures(pipeline, "powerschool")

    assert stored == {}


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
            PowerSchoolTable(name="students", cursor_column="transaction_date"),
            PowerSchoolTable(name="gen", cursor_column=None),
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
        [PowerSchoolTable(name="students", cursor_column="transaction_date")]
    )

    from dagster import validate_run_config

    assert validate_run_config(job, {})
