"""Checks file loading."""

import datetime as dt

import pytest
import yaml

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import config

BASE = {
    "dashboard": "attendance_dashboard",
    "workbook": "Attendance Dashboard",
    "workbook_luid": "87c13e78",
    "review_project_luid": "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc",
    "dashboards": ["Overview"],
    "datasource": "rpt (ds)",
    "dashboard_table": "p.d.t",
    "period_start": "2026-07-01",
    "window": {
        "start": "15:30",
        "end": "06:00",
        "extract_after": "15:00",
        "tz": "America/New_York",
    },
    "cost_cap_gb": 50,
    "cube": {
        "view": "v",
        "date": "attendance_date",
        "members": ["lea_student_identifier"],
    },
    "rows": {
        "student_key": "student",
        "date_key": "day",
        "scope_key": "school",
        "key": {
            "student": {"tableau": "student_number", "cube": "lea_student_identifier"},
            "day": {"tableau": "calendardate", "cube": "attendance_date"},
            "school": {
                "tableau": "school_abbreviation",
                "cube": "locations_abbreviation",
            },
        },
        "compare": {"is_absent": {"tableau": "is_absent", "cube": "is_absent"}},
    },
    "cuts": [{"id": "default"}],
}


def _write(tmp_path, **over):
    data = {**BASE, **over}
    p = tmp_path / "c.yml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


def test_loads_a_minimal_checks_file(tmp_path):
    c = config.load_checks(_write(tmp_path))
    assert c.period_start == dt.date(2026, 7, 1)
    assert c.window.start == dt.time(15, 30) and c.window.tz == "America/New_York"
    assert [e.name for e in c.key] == ["student", "day", "school"]
    assert c.quiet_minutes == (0, 10)
    assert c.cuts[0].id == "default" and c.causes == ()


def test_first_cut_must_be_a_bare_default(tmp_path):
    with pytest.raises(config.ConfigError, match="first cut"):
        config.load_checks(_write(tmp_path, cuts=[{"id": "x", "filters": {"A": "1"}}]))


def test_cause_needs_a_known_owner_and_a_free_id(tmp_path):
    bad_owner = [{"id": "x", "description": "d", "where": "true", "owner": "me"}]
    with pytest.raises(config.ConfigError, match="owner"):
        config.load_checks(_write(tmp_path, causes=bad_owner))
    reserved = [
        {"id": "unexplained", "description": "d", "where": "true", "owner": "cube"}
    ]
    with pytest.raises(config.ConfigError, match="reserved"):
        config.load_checks(_write(tmp_path, causes=reserved))


def test_student_and_date_keys_must_be_key_parts(tmp_path):
    rows = {**BASE["rows"], "student_key": "pupil"}
    with pytest.raises(config.ConfigError, match="student_key"):
        config.load_checks(_write(tmp_path, rows=rows))


def test_sheet_maps_read_dims_measures_and_view(tmp_path):
    sheets = {
        "ADA by School": {
            "students": "Student Count",
            "dims": {
                "School": {
                    "tableau": "school_abbreviation",
                    "cube": "locations_abbreviation",
                    "cube_column": "locations_abbreviation",
                }
            },
            "measures": {"ADA": {"cube": "avg_daily_attendance"}},
        }
    }
    c = config.load_checks(_write(tmp_path, sheets=sheets))
    s = c.sheets["ADA by School"]
    assert s.view == "v" and s.students == "Student Count"
    assert s.dims["School"].cube == "locations_abbreviation"
    assert s.measures["ADA"].scale == 1.0


def test_side_sql_and_lit():
    assert config.side_sql("grade_level", "t_") == '"t_grade_level"'
    assert config.side_sql('"{p}grade_level" >= 9', "c_") == '"c_grade_level" >= 9'
    assert config.lit("O'Neil") == "'O''Neil'"
    assert config.lit(None) == "NULL"
