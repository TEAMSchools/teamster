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
        "members": [
            "lea_student_identifier",
            "attendance_date",
            "locations_abbreviation",
            "is_absent",
        ],
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


def test_scope_key_needs_a_bare_cube_member(tmp_path):
    rows = {
        **BASE["rows"],
        "key": {
            **BASE["rows"]["key"],
            "school": {
                "tableau": "school_abbreviation",
                "cube": 'upper("{p}locations_abbreviation")',
            },
        },
    }
    with pytest.raises(config.ConfigError, match="scope_key"):
        config.load_checks(_write(tmp_path, rows=rows))


def test_defaults_load_and_need_a_mapped_filter(tmp_path):
    filters = {"Year": {"tableau": "academic_year", "cube": "academic_year"}}
    c = config.load_checks(_write(tmp_path, filters=filters, defaults={"Year": 2026}))
    assert c.defaults == {"Year": "2026"}
    with pytest.raises(config.ConfigError, match="defaults: Grade"):
        config.load_checks(_write(tmp_path, filters=filters, defaults={"Grade": 9}))


def test_sheets_whose_export_files_would_collide_are_refused(tmp_path):
    sheets = {"ADA by School": {}, "ADA-by-School": {}}
    with pytest.raises(config.ConfigError, match="ADA by School.*ADA-by-School"):
        config.load_checks(_write(tmp_path, sheets=sheets))
    cuts = [{"id": "default"}, {"id": "a b"}, {"id": "a-b"}]
    with pytest.raises(config.ConfigError, match="a b.*a-b"):
        config.load_checks(_write(tmp_path, cuts=cuts))


@pytest.mark.parametrize(
    "over",
    [
        {"filters": {"Grade": {"tableau": "g", "cube": "g", "cube_column": "grade"}}},
        {
            "sheets": {
                "S": {"dims": {"Grade": {"tableau": "g", "cube_column": "grade"}}}
            }
        },
        {"params": {"P": {"v": {"cube_column": "grade"}}}},
        {"params": {"P": {"v": {"cube_column": '"{p}grade" >= 9'}}}},
        {
            "rows": {
                **BASE["rows"],
                "compare": {"is_absent": {"tableau": "is_absent", "cube": "grade"}},
            }
        },
    ],
)
def test_every_cube_column_must_be_captured(tmp_path, over):
    with pytest.raises(config.ConfigError, match="grade"):
        config.load_checks(_write(tmp_path, **over))


def test_cube_sql_over_captured_columns_is_accepted(tmp_path):
    params = {"P": {"v": {"cube_column": '"{p}is_absent" = 1'}}}
    assert config.load_checks(_write(tmp_path, params=params)).params["P"]["v"]


def test_a_single_item_list_default_loads_as_its_value(tmp_path):
    filters = {"Year": {"tableau": "Year"}}
    c = config.load_checks(
        _write(tmp_path, filters=filters, defaults={"Year": ["2026"]})
    )
    assert c.defaults == {"Year": "2026"}


@pytest.mark.parametrize("bad", [[], ["2025", "2026"]])
def test_a_multi_value_or_empty_list_default_is_refused(tmp_path, bad):
    filters = {"Year": {"tableau": "Year"}}
    with pytest.raises(
        config.ConfigError, match="defaults.Year must be a single value"
    ):
        config.load_checks(_write(tmp_path, filters=filters, defaults={"Year": bad}))
