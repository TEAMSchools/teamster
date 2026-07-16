"""Unit tests for the probe-gated PowerSchool dlt factory (no external deps)."""

import pathlib
from datetime import datetime

import yaml

from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolTable,
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
        "kipppaterson/powerschool/students",
        "kipppaterson/powerschool/users",
        "kipppaterson/powerschool/test",
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
