"""Checks file loading."""

import datetime as dt
from pathlib import Path

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
    "cost_cap_usd": 5,
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
    assert c.defaults == {"Year": ("2026",)}
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


def test_a_single_item_list_default_loads_as_a_one_tuple(tmp_path):
    filters = {"Year": {"tableau": "Year"}}
    c = config.load_checks(
        _write(tmp_path, filters=filters, defaults={"Year": ["2026"]})
    )
    assert c.defaults == {"Year": ("2026",)}


def test_a_list_default_of_three_loads_as_a_three_tuple(tmp_path):
    filters = {"Region": {"tableau": "Region"}}
    regions = ["Camden", "Newark", "Paterson"]
    c = config.load_checks(
        _write(tmp_path, filters=filters, defaults={"Region": regions})
    )
    assert c.defaults == {"Region": ("Camden", "Newark", "Paterson")}


def test_an_empty_list_default_is_refused(tmp_path):
    filters = {"Year": {"tableau": "Year"}}
    with pytest.raises(config.ConfigError, match="defaults.Year is an empty list"):
        config.load_checks(_write(tmp_path, filters=filters, defaults={"Year": []}))


COMMITTED = (
    Path(__file__).parents[3]
    / ".claude/skills/cube-dashboard/checks/attendance_dashboard.yml"
)


def test_a_skeleton_loads_for_plan_only(tmp_path):
    # A checks file as it stands before plan: no data source, no dashboards.
    data = yaml.safe_load(COMMITTED.read_text())
    data.update(datasource="", dashboards=[])
    skeleton = tmp_path / "skeleton.yml"
    skeleton.write_text(yaml.safe_dump(data, sort_keys=False))
    c = config.load_checks(skeleton, for_plan=True)
    assert c.datasource == "" and c.dashboards == ()
    with pytest.raises(config.ConfigError, match="datasource"):
        config.load_checks(skeleton)


def test_the_committed_attendance_checks_file_loads():
    assert config.load_checks(COMMITTED).dashboards == ("Attendance Rollup",)


def test_cost_cap_defaults_to_five_dollars(tmp_path):
    data = {k: v for k, v in BASE.items() if k != "cost_cap_usd"}
    p = tmp_path / "c.yml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    assert config.load_checks(p).cost_cap_usd == 5.0


def test_cost_cap_in_gigabytes_is_refused(tmp_path):
    with pytest.raises(config.ConfigError, match="cost_cap_usd"):
        config.load_checks(_write(tmp_path, cost_cap_gb=50))


def test_a_cause_is_inert_only_when_it_says_so(tmp_path):
    causes = [
        {"id": "a", "description": "d", "where": "true", "owner": "dashboard"},
        {
            "id": "b",
            "description": "d",
            "where": "true",
            "owner": "dashboard",
            "inert": True,
        },
    ]
    c = config.load_checks(_write(tmp_path, causes=causes))
    assert [x.inert for x in c.causes] == [False, True]
    bad = [{**causes[1], "inert": "yes"}]
    with pytest.raises(config.ConfigError, match="inert"):
        config.load_checks(_write(tmp_path, causes=bad))


def _metric(values):
    sheets = {
        "S": {"measures": {"M": {"cube": "avg_daily_attendance", "param": "Metric"}}}
    }
    return {"sheets": sheets, "params": {"Metric": values}}


def test_a_parameter_value_loads_its_measure_view_and_renames(tmp_path):
    chronic = {
        "measure": "pct_chronically_absent",
        "view": "p",
        "rename": {"dates_academic_year": "academic_year"},
    }
    c = config.load_checks(_write(tmp_path, **_metric({"Chronic": chronic})))
    pv = c.params["Metric"]["Chronic"]
    assert (pv.measure, pv.view) == ("pct_chronically_absent", "p")
    assert pv.rename == {"dates_academic_year": "academic_year"}
    assert c.sheets["S"].measures["M"].param == "Metric"


def test_a_swapped_measure_needs_a_measure_on_every_listed_value(tmp_path):
    with pytest.raises(config.ConfigError, match="Metric.*On-Time.*measure"):
        config.load_checks(_write(tmp_path, **_metric({"On-Time": {"view": "p"}})))


def test_a_measure_cannot_name_an_unknown_parameter(tmp_path):
    over = _metric({})
    over["params"] = {}
    with pytest.raises(config.ConfigError, match="param Metric"):
        config.load_checks(_write(tmp_path, **over))


def _coverage(**over):
    """Overrides for a sheet whose measure swaps on a parameter, plus the 3 new sections."""
    sheets = {
        "S": {
            "measures": {
                "Avg. Attendance Metric": {
                    "cube": "avg_daily_attendance",
                    "param": "Attendance Metric",
                }
            }
        }
    }
    params = {
        "Attendance Metric": {
            "Chronic Absenteeism": {"measure": "pct_chronically_absent", "view": "pv"},
            "On-Time": {"measure": "pct_ontime"},
        }
    }
    must_cover = [
        {
            "name": "Percent Chronic Absenteeism",
            "source": "https://example.test/1",
            "cube": {"member": "pct_chronically_absent", "view": "pv"},
            "tableau": {
                "column": "Avg. Attendance Metric",
                "param": {"Attendance Metric": "Chronic Absenteeism"},
            },
            "rows": [],
        }
    ]
    probes = [
        {
            "id": "chronic-probe",
            "measure": "Avg. Attendance Metric",
            "param": {"Attendance Metric": "Chronic Absenteeism"},
            "dashboard": "select 1 from {extract} where {where}",
            "candidate": "select 2 from {extract} where {where}",
        }
    ]
    decisions = [
        {
            "measure": "Avg. Attendance Metric",
            "param": {"Attendance Metric": "Chronic Absenteeism"},
            "owner": "dashboard",
            "rule": "The dashboard drops transfers.",
            "probe": "chronic-probe",
            "task": "",
        }
    ]
    data = {
        "sheets": sheets,
        "params": params,
        "must_cover": must_cover,
        "probes": probes,
        "decisions": decisions,
    }
    data.update(over)
    return data


def test_must_cover_probes_and_decisions_load(tmp_path):
    c = config.load_checks(_write(tmp_path, **_coverage()))
    assert c.must_cover == (
        config.MustCover(
            name="Percent Chronic Absenteeism",
            source="https://example.test/1",
            cube=("pct_chronically_absent", "pv"),
            column="Avg. Attendance Metric",
            param=("Attendance Metric", "Chronic Absenteeism"),
            rows=(),
        ),
    )
    assert c.probes[0].param == ("Attendance Metric", "Chronic Absenteeism")
    assert c.probes[0].id == "chronic-probe"
    d = c.decisions[0]
    assert (d.owner, d.probe, d.cuts, d.sheets, d.task) == (
        "dashboard",
        "chronic-probe",
        (),
        (),
        "",
    )
    assert "decisions" in config.MAPPING_EXCLUDED


def test_a_must_cover_member_must_match_the_mapping(tmp_path):
    over = _coverage()
    over["must_cover"][0]["cube"]["member"] = "pct_ontime"
    with pytest.raises(config.ConfigError, match="must_cover.*pct_ontime"):
        config.load_checks(_write(tmp_path, **over))


def test_a_must_cover_row_name_must_be_a_compare_name(tmp_path):
    over = _coverage()
    over["must_cover"][0]["rows"] = ["nope"]
    with pytest.raises(config.ConfigError, match="must_cover.*nope"):
        config.load_checks(_write(tmp_path, **over))


def test_a_decision_needs_a_mapped_measure_and_value(tmp_path):
    over = _coverage()
    over["decisions"][0]["param"] = {"Attendance Metric": "Nope"}
    with pytest.raises(config.ConfigError, match="decisions.*Nope"):
        config.load_checks(_write(tmp_path, **over))


def test_a_dashboard_or_cube_decision_names_a_known_probe(tmp_path):
    over = _coverage()
    over["decisions"][0]["probe"] = "missing"
    with pytest.raises(config.ConfigError, match="decisions.*missing"):
        config.load_checks(_write(tmp_path, **over))
    over = _coverage()
    over["decisions"][0].update(owner="accepted", probe=None)
    with pytest.raises(config.ConfigError, match="accepted"):
        config.load_checks(_write(tmp_path, **over))
    over["decisions"][0]["sheets"] = ["S"]
    c = config.load_checks(_write(tmp_path, **over))
    assert c.decisions[0].sheets == ("S",)


def test_a_selector_value_may_carry_a_null_measure(tmp_path):
    over = _metric({"HS Alt": {"measure": None}})
    c = config.load_checks(_write(tmp_path, **over))
    assert c.params["Metric"]["HS Alt"].measure is None
    with pytest.raises(config.ConfigError, match="needs a measure"):
        config.load_checks(_write(tmp_path, **_metric({"HS Alt": {"view": "p"}})))


@pytest.mark.parametrize("owner", ["dashboard", "cube"])
def test_a_dashboard_or_cube_decision_needs_a_probe(tmp_path, owner):
    over = _coverage()
    over["decisions"][0].update(owner=owner, probe=None)
    with pytest.raises(config.ConfigError, match=f"decisions.*{owner}.*probe"):
        config.load_checks(_write(tmp_path, **over))


def test_a_selector_value_records_whether_it_gave_a_measure(tmp_path):
    over = _metric({"HS Alt": {"measure": None}, "Chronic": {"measure": "m"}})
    pvs = config.load_checks(_write(tmp_path, **over)).params["Metric"]
    assert (pvs["HS Alt"].swaps_measure, pvs["Chronic"].swaps_measure) == (True, True)


def test_a_must_cover_entry_with_no_cube_member_needs_rows(tmp_path):
    over = _coverage()
    over["must_cover"][0]["cube"] = None
    with pytest.raises(config.ConfigError, match="must_cover.*Percent Chronic.*rows:"):
        config.load_checks(_write(tmp_path, **over))


def test_a_must_cover_param_must_be_a_listed_value_of_its_mapped_measure(tmp_path):
    over = _coverage()
    over["must_cover"][0]["tableau"]["param"] = {"Attendance Metric": "Nope"}
    with pytest.raises(
        config.ConfigError, match="must_cover Percent Chronic.*Nope.*Attendance Metric"
    ):
        config.load_checks(_write(tmp_path, **over))
    over = _coverage()
    over["must_cover"][0]["tableau"]["param"] = {
        "Other Selector": "Chronic Absenteeism"
    }
    with pytest.raises(config.ConfigError, match="must_cover Percent Chronic.*Other"):
        config.load_checks(_write(tmp_path, **over))


def test_a_must_cover_param_on_an_unmapped_column_still_loads(tmp_path):
    over = _coverage()
    over["must_cover"][0]["tableau"] = {
        "column": "Not Mapped",
        "param": {"Attendance Metric": "Nope"},
    }
    c = config.load_checks(_write(tmp_path, **over))
    assert c.must_cover[0].param == ("Attendance Metric", "Nope")


def test_a_must_cover_member_cannot_sit_on_a_null_mapping(tmp_path):
    over = _coverage()
    over["params"]["Attendance Metric"]["Chronic Absenteeism"] = {"measure": None}
    with pytest.raises(
        config.ConfigError, match="must_cover Percent Chronic.*sheet S.*no Cube member"
    ):
        config.load_checks(_write(tmp_path, **over))
    over = _coverage()
    over["sheets"]["S"]["measures"]["Avg. Attendance Metric"] = {"cube": None}
    over["must_cover"][0]["tableau"].pop("param")
    with pytest.raises(
        config.ConfigError, match="must_cover Percent Chronic.*sheet S.*no Cube member"
    ):
        config.load_checks(_write(tmp_path, **over))
