"""Cells layer: display precision, verdicts, predicates, and planted cell gaps."""

import datetime as dt

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import cells, config


def test_display_equal_reads_precision_from_the_export():
    assert cells.display_equal("94.2%", 0.94213)
    assert not cells.display_equal("94.2%", 0.9436)
    assert cells.display_equal("1,204", 1204.0)
    assert cells.display_equal("0.94213", 0.942130000001)
    assert cells.display_equal("", None) and not cells.display_equal("", 0.5)


def test_display_equal_rounds_half_up():
    assert cells.display_equal("94.3%", 0.9425)


def test_parse_export_pivots_measure_names_and_drops_totals():
    data = (
        "School,Measure Names,Measure Values\n"
        "Rise,ADA,94.2%\nRise,Students,300\nGrand Total,ADA,93.0%\n"
    ).encode("utf-8-sig")
    assert cells.parse_export(data) == [
        {"School": "Rise", "ADA": "94.2%", "Students": "300"}
    ]


def test_norm_value_reads_tableau_and_cube_formats():
    assert cells.norm_value("10/6/2026") == "2026-10-06"
    assert cells.norm_value("2026-10-06T00:00:00.000") == "2026-10-06"
    assert cells.norm_value("1,204") == "1204"
    assert cells.norm_value("Null") is None


@pytest.mark.parametrize(
    ("equal", "buckets", "want"),
    [
        (True, [("match", None, 5, 2)], cells.PASS),
        (True, [("match", None, 5, 2), ("cube_only", "x", 1, 1)], cells.COINCIDENTAL),
        (False, [("match", None, 5, 2), ("dashboard_only", None, 1, 1)], cells.ROW_GAP),
        (False, [("match", None, 5, 2)], cells.FORMULA_GAP),
        (False, [], cells.NO_ROWS),
    ],
)
def test_verdict(equal, buckets, want):
    assert cells.verdict(equal, buckets) == want


def _checks(**over):
    base = dict(
        dashboard="d",
        workbook="w",
        workbook_luid="l",
        review_project_luid="p",
        dashboards=("Overview",),
        datasource="ds",
        dashboard_table="p.d.t",
        period_start=dt.date(2026, 7, 1),
        window=config.Window(
            dt.time(15, 30), dt.time(6), dt.time(15), "America/New_York"
        ),
        cost_cap_gb=50,
        quiet_minutes=(0, 10),
        cube=config.CubeRows("v", "attendance_date", ()),
        key=(
            config.Expr("student", "student_number", "lea_student_identifier"),
            config.Expr("day", "calendardate", "attendance_date"),
        ),
        compare=(),
        labels=(),
        student_key="student",
        date_key="day",
        scope_key=None,
        causes=(),
        filters={
            "Region": config.FieldMap(
                "Region", "region", "regions_region_name", "regions_region_name"
            )
        },
        params={},
        sheets={
            "ADA": config.SheetMap(
                "ADA",
                "v",
                dims={
                    "School": config.FieldMap(
                        "School",
                        "school_abbreviation",
                        "locations_abbreviation",
                        "locations_abbreviation",
                    )
                },
                measures={"ADA": config.MeasureMap("ADA", "avg_daily_attendance")},
                students="Students",
            )
        },
        cuts=(config.Cut("default"), config.Cut("filter-region", {"Region": "Camden"})),
        excluded_sheets={},
    )
    base.update(over)
    return config.Checks(**base)


def test_cube_query_maps_filters_dims_and_adds_count_students():
    q = cells.cube_query(
        _checks(), "ADA", config.Cut("filter-region", {"Region": "Camden"}), {}
    )
    assert q["measures"] == ["v.avg_daily_attendance", "v.count_students"]
    assert q["dimensions"] == ["v.locations_abbreviation"]
    assert q["filters"] == [
        {"member": "v.regions_region_name", "operator": "equals", "values": ["Camden"]}
    ]


def test_cube_query_refuses_an_unmapped_filter():
    with pytest.raises(cells.MappingGap, match="Grade"):
        cells.cube_query(_checks(), "ADA", config.Cut("x", {"Grade": "9"}), {})


def _rows_table(ws, extra=()):
    """A minimal rows table as Task 5 builds it."""
    ws.execute(
        "create temporary table rows (in_t bool, in_c bool, k_student bigint, k_day date, base text, cause text, "
        "t_region text, t_school_abbreviation text, c_regions_region_name text, c_locations_abbreviation text)"
    )
    vals = [
        "(true, true, 1, '2026-10-06', 'match', null, 'Newark', 'Rise', 'Newark', 'Rise')",
        "(true, true, 2, '2026-10-06', 'match', null, 'Newark', 'Rise', 'Newark', 'Rise')",
        "(true, true, 3, '2026-10-06', 'match', null, 'Camden', 'LSP', 'Camden', 'LSP')",
        *extra,
    ]
    ws.execute("insert into rows values " + ", ".join(vals))


def _judge(tmp_path, exports, answers, checks=None, extra=(), manifest=None):
    pytest.importorskip("tableauhyperapi")
    # trunk-ignore(pyright/reportAttributeAccessIssue)
    from cube_validate import hyper

    with hyper.Workspace(tmp_path / "a.hyper", {}) as ws:
        _rows_table(ws, extra)
        return cells.judge(
            ws,
            checks or _checks(),
            manifest or {"cuts": {}},
            answers,
            lambda cut, sheet: exports.get((cut, sheet)),
        )


def _ans(cut, rows):
    return {
        cells.answer_key(cut, "ADA"): {
            "data": rows,
            "last_refresh": "x",
            "sql": "s",
            "query": {},
        }
    }


def test_matching_cells_pass(tmp_path):
    exports = {
        ("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n",
        ("filter-region", "ADA"): b"School,ADA,Students\nLSP,90.0%,1\n",
    }
    answers = {
        **_ans(
            "default",
            [
                {"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
                {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"},
            ],
        ),
        **_ans(
            "filter-region",
            [{"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"}],
        ),
    }
    got = _judge(tmp_path, exports, answers)
    assert [c.verdict for c in got] == [cells.PASS] * 3


def test_shifted_cube_value_is_a_formula_gap_on_that_cell_only(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n"}
    answers = _ans(
        "default",
        [
            {"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.95"},
            {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"},
        ],
    )
    checks = _checks(cuts=(config.Cut("default"),))
    got = {
        c.dims["School"]: c.verdict for c in _judge(tmp_path, exports, answers, checks)
    }
    assert got == {"Rise": cells.FORMULA_GAP, "LSP": cells.PASS}


def test_row_gap_lists_its_buckets(tmp_path):
    extra = [
        "(true, false, 4, '2026-10-06', 'dashboard_only', 'unexplained', 'Newark', 'Rise', null, null)"
    ]
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,3\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.95"}],
    )
    checks = _checks(cuts=(config.Cut("default"),))
    (c,) = [
        x
        for x in _judge(tmp_path, exports, answers, checks, extra)
        if x.measure == "ADA"
    ]
    assert c.verdict == cells.ROW_GAP
    assert ("dashboard_only", "unexplained", 1, 1) in c.buckets and c.students == (3, 2)


def test_ignored_filter_is_never_judged(tmp_path):
    same = b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n"
    exports = {("default", "ADA"): same, ("filter-region", "ADA"): same}
    answers = {**_ans("default", []), **_ans("filter-region", [])}
    got = [c for c in _judge(tmp_path, exports, answers) if c.cut == "filter-region"]
    assert got and all(c.verdict == cells.FILTER_IGNORED for c in got)


def test_wrong_student_count_makes_the_cut_unproven(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,7\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}],
    )
    got = _judge(tmp_path, exports, answers, _checks(cuts=(config.Cut("default"),)))
    assert {c.verdict for c in got} == {cells.UNPROVEN}


def test_cut_without_a_student_count_is_unproven_with_one_reason(tmp_path):
    sheet = _checks().sheets["ADA"]
    checks = _checks(
        cuts=(config.Cut("default"),),
        sheets={"ADA": config.SheetMap("ADA", "v", sheet.dims, sheet.measures, None)},
    )
    exports = {("default", "ADA"): b"School,ADA\nRise,94.2%\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}],
    )
    got = _judge(tmp_path, exports, answers, checks)
    assert {(c.verdict, c.reason) for c in got} == {
        (cells.UNPROVEN, "no sheet in this cut shows a student count")
    }


def test_cell_outside_the_captured_rows_is_not_a_formula_gap(tmp_path):
    exports = {
        ("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nHatch,88.0%,0\n"
    }
    answers = _ans(
        "default",
        [
            {"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
            {"v.locations_abbreviation": "Hatch", "v.avg_daily_attendance": "0.87"},
        ],
    )
    got = {
        c.dims["School"]: c.verdict
        for c in _judge(
            tmp_path, exports, answers, _checks(cuts=(config.Cut("default"),))
        )
        if c.measure == "ADA"
    }
    assert got["Hatch"] == cells.NO_ROWS


def test_unmapped_measure_has_no_cube_counterpart(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students,Tardy\nRise,94.2%,2,3.0%\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}],
    )
    got = {
        c.measure: c.verdict
        for c in _judge(
            tmp_path, exports, answers, _checks(cuts=(config.Cut("default"),))
        )
    }
    assert got["Tardy"] == cells.NO_COUNTERPART and got["ADA"] == cells.PASS
