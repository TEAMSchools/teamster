"""Cells layer: display precision, verdicts, predicates, and planted cell gaps."""

import datetime as dt
from dataclasses import replace

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
        cost_cap_usd=5.0,
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


def _rows_table(ws, extra=(), rise_cube="Rise"):
    """A minimal rows table as Task 5 builds it."""
    ws.execute(
        "create temporary table rows (in_t bool, in_c bool, k_student bigint, k_day date, base text, cause text, "
        "t_region text, t_school_abbreviation text, c_regions_region_name text, c_locations_abbreviation text)"
    )
    vals = [
        f"(true, true, 1, '2026-10-06', 'match', null, 'Newark', 'Rise', 'Newark', '{rise_cube}')",
        f"(true, true, 2, '2026-10-06', 'match', null, 'Newark', 'Rise', 'Newark', '{rise_cube}')",
        "(true, true, 3, '2026-10-06', 'match', null, 'Camden', 'LSP', 'Camden', 'LSP')",
        *extra,
    ]
    ws.execute("insert into rows values " + ", ".join(vals))


def _judge(
    tmp_path, exports, answers, checks=None, extra=(), manifest=None, rise_cube="Rise"
):
    pytest.importorskip("tableauhyperapi")
    # trunk-ignore(pyright/reportAttributeAccessIssue)
    from cube_validate import hyper

    with hyper.Workspace(tmp_path / "a.hyper", {}) as ws:
        _rows_table(ws, extra, rise_cube)
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


def _with_sheet(**over):
    """Checks with one default cut and the ADA sheet's fields overridden."""
    sheet = _checks().sheets["ADA"]
    f = {
        "dims": sheet.dims,
        "measures": sheet.measures,
        "students": sheet.students,
        **over,
    }
    return _checks(
        cuts=(config.Cut("default"),),
        sheets={
            "ADA": config.SheetMap("ADA", "v", f["dims"], f["measures"], f["students"])
        },
    )


_ANS_RISE = [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}]


def test_unmapped_measure_has_no_cube_counterpart(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students,Tardy\nRise,94.2%,2,3.0%\n"}
    measures = {
        "ADA": config.MeasureMap("ADA", "avg_daily_attendance"),
        "Tardy": config.MeasureMap("Tardy", None),
    }
    got = {
        c.measure: c.verdict
        for c in _judge(
            tmp_path,
            exports,
            _ans("default", _ANS_RISE),
            _with_sheet(measures=measures),
        )
    }
    assert got["Tardy"] == cells.NO_COUNTERPART and got["ADA"] == cells.PASS


def test_undeclared_column_makes_the_row_unjudgeable(tmp_path):
    exports = {
        (
            "default",
            "ADA",
        ): b"School,Grade,ADA,Students\nRise,5,90.0%,1\nRise,6,98.0%,1\n"
    }
    got = _judge(tmp_path, exports, _ans("default", _ANS_RISE), _with_sheet())
    assert got and {(c.verdict, c.reason) for c in got} == {
        (cells.NO_COUNTERPART, "column not mapped: Grade")
    }


def test_dim_without_a_cube_column_is_unproven_not_a_crash(tmp_path):
    dims = {
        "School": config.FieldMap(
            "School", "school_abbreviation", "locations_abbreviation", None
        )
    }
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\n"}
    got = _judge(tmp_path, exports, _ans("default", _ANS_RISE), _with_sheet(dims=dims))
    assert got and all(
        c.verdict == cells.UNPROVEN and "not mapped: School" in c.reason for c in got
    )


def test_label_mismatch_is_unproven_on_both_sides(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "RISE", "v.avg_daily_attendance": "0.942"}],
    )
    got = _judge(tmp_path, exports, answers, _with_sheet(), rise_cube="RISE")
    by = {c.tableau is None: c for c in got}
    assert not {c.verdict for c in got} & {cells.FORMULA_GAP, cells.ROW_GAP}
    assert by[False].verdict == cells.UNPROVEN
    assert by[False].reason == "Cube answer has no mark for these labels"
    assert by[True].verdict == cells.UNPROVEN
    assert (
        by[True].reason == "Tableau shows no mark for labels the extract has rows for"
    )


def test_dashboard_only_row_with_no_cube_mark_is_a_row_gap(tmp_path):
    extra = [
        "(true, false, 9, '2026-10-06', 'dashboard_only', 'unexplained', 'Newark', 'Hatch', null, null)"
    ]
    exports = {
        ("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nHatch,88.0%,1\n"
    }
    got = {
        c.dims["School"]: c
        for c in _judge(
            tmp_path, exports, _ans("default", _ANS_RISE), _with_sheet(), extra
        )
    }
    assert got["Hatch"].verdict == cells.ROW_GAP
    assert ("dashboard_only", "unexplained", 1, 1) in got["Hatch"].buckets


def test_dim_with_cube_column_but_no_cube_member_is_unproven(tmp_path):
    dims = {
        **_checks().sheets["ADA"].dims,
        "Grade": config.FieldMap("Grade", "region", None, "x"),
    }
    exports = {("default", "ADA"): b"School,Grade,ADA,Students\nRise,Newark,90.0%,2\n"}
    got = _judge(tmp_path, exports, _ans("default", _ANS_RISE), _with_sheet(dims=dims))
    assert got and {c.verdict for c in got} == {cells.UNPROVEN}
    assert all("not mapped: Grade: no Cube member" == c.reason for c in got)


def test_click_target_sheet_without_a_count_is_not_proven_by_another_sheet(tmp_path):
    checks = _checks(
        cuts=(config.Cut("default"), config.Cut("click")),
        sheets={
            **_checks().sheets,
            "Tgt": config.SheetMap(
                "Tgt",
                "v",
                _checks().sheets["ADA"].dims,
                {"ADA": config.MeasureMap("ADA", "avg_daily_attendance")},
                None,
            ),
        },
    )
    exports = {
        ("click", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n",
        ("click", "Tgt"): b"School,ADA\nLSP,90.0%\n",
    }
    rows = [
        {"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
        {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"},
    ]
    answers = {
        cells.answer_key("click", "ADA"): {"data": rows},
        cells.answer_key("click", "Tgt"): {"data": rows[1:]},
    }
    manifest = {
        "cuts": {
            "click": {"click_filters": {"Region": "Camden"}, "click_targets": ["Tgt"]}
        }
    }
    got = _judge(tmp_path, exports, answers, checks, manifest=manifest)
    tgt = [c for c in got if c.sheet == "Tgt"]
    assert tgt and all(
        c.verdict == cells.UNPROVEN
        and c.reason == "no student count proves this sheet's filters"
        for c in tgt
    )
    assert all(c.verdict == cells.PASS for c in got if c.sheet == "ADA")


@pytest.mark.parametrize("cube_ada", ["0.942", "0.95"])
def test_cell_with_rows_outside_the_period_has_no_captured_rows(tmp_path, cube_ada):
    extra = [
        "(true, false, 4, '2025-10-06', 'outside_period', 'outside_period', 'Newark', 'Rise', null, null)"
    ]
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,3\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": cube_ada}],
    )
    (c,) = _judge(tmp_path, exports, answers, _with_sheet(), extra)
    assert (c.verdict, c.reason) == (
        cells.NO_ROWS,
        "some of this cell's rows fall outside the captured period",
    )


def test_cell_with_rows_outside_cube_scope_is_unproven(tmp_path):
    extra = [
        "(true, false, 4, '2026-10-06', 'outside_scope', 'outside_scope', 'Newark', 'Rise', null, null)"
    ]
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,3\n"}
    answers = _ans(
        "default",
        [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.95"}],
    )
    (c,) = _judge(tmp_path, exports, answers, _with_sheet(), extra)
    assert (c.verdict, c.reason) == (
        cells.UNPROVEN,
        "rows outside Cube's scope for this identity",
    )


def test_display_equal_accepts_exact_halves_despite_float_noise():
    assert cells.display_equal("94.3%", 377 / 400)
    assert cells.display_equal("0.5%", 0.0045)
    assert not cells.display_equal("94.2%", 0.9436)


def test_defaults_apply_to_every_cut_and_a_cut_filter_overrides_them():
    import dataclasses

    checks = dataclasses.replace(_checks(), defaults={"Region": ("Newark",)})
    sm = "ADA"
    q = cells.cube_query(checks, sm, config.Cut("default"), {})
    assert q["filters"] == [
        {"member": "v.regions_region_name", "operator": "equals", "values": ["Newark"]}
    ]
    q = cells.cube_query(checks, sm, config.Cut("c", {"Region": "Camden"}), {})
    assert q["filters"] == [
        {"member": "v.regions_region_name", "operator": "equals", "values": ["Camden"]}
    ]
    assert cells._cut_preds(checks, config.Cut("default"), {}, "t") == [
        "(\"t_region\" = 'Newark')"
    ]
    assert cells._cut_preds(checks, config.Cut("c", {"Region": "Camden"}), {}, "c") == [
        "(\"c_regions_region_name\" = 'Camden')"
    ]


def test_default_filter_values_prove_the_default_cut_and_its_repeats(tmp_path):
    import dataclasses

    checks = dataclasses.replace(
        _with_sheet(dims={}),
        defaults={"Region": ("Newark",)},
        cuts=(config.Cut("default"), config.Cut("same", {"Region": "Newark"})),
    )
    total = b"ADA,Students\n94.2%,2\n"
    exports = {("default", "ADA"): total, ("same", "ADA"): total}
    row = [{"v.avg_daily_attendance": "0.942"}]
    answers = {**_ans("default", row), **_ans("same", row)}
    got = _judge(tmp_path, exports, answers, checks)
    assert [(c.cut, c.verdict) for c in got] == [
        ("default", cells.PASS),
        ("same", cells.PASS),
    ]


def test_multi_value_default_reads_as_in_on_both_sides_and_in_cubes_equals():
    import dataclasses

    three = ("Camden", "Newark", "Paterson")
    checks = dataclasses.replace(_checks(), defaults={"Region": three})
    default = config.Cut("default")
    q = cells.cube_query(checks, "ADA", default, {})
    assert q["filters"] == [
        {
            "member": "v.regions_region_name",
            "operator": "equals",
            "values": list(three),
        }
    ]
    in_list = "('Camden', 'Newark', 'Paterson')"
    assert cells._cut_preds(checks, default, {}, "t") == [f'("t_region" in {in_list})']
    assert cells._cut_preds(checks, default, {}, "c") == [
        f'("c_regions_region_name" in {in_list})'
    ]


def test_a_cut_filter_overrides_a_multi_value_default():
    import dataclasses

    checks = dataclasses.replace(
        _checks(), defaults={"Region": ("Camden", "Newark", "Paterson")}
    )
    cut = config.Cut("c", {"Region": "Camden"})
    assert cells.cube_query(checks, "ADA", cut, {})["filters"] == [
        {"member": "v.regions_region_name", "operator": "equals", "values": ["Camden"]}
    ]
    assert cells._cut_preds(checks, cut, {}, "t") == ["(\"t_region\" = 'Camden')"]


def test_all_among_defaults_means_no_default():
    import dataclasses

    checks = dataclasses.replace(_checks(), defaults={"Region": (cells.ALL,)})
    assert cells.cube_query(checks, "ADA", config.Cut("default"), {})["filters"] == []
    assert cells._cut_preds(checks, config.Cut("default"), {}, "t") == []


def test_parse_export_drops_all_subtotal_rows():
    data = b"Grade Level,School,ADA\n11,NCA,87%\n11,All,89%\nAll,All,90%\n"
    assert cells.parse_export(data) == [
        {"Grade Level": "11", "School": "NCA", "ADA": "87%"}
    ]


@pytest.mark.parametrize(
    ("equal", "want"),
    [(True, cells.PASS), (False, cells.FORMULA_GAP)],
)
def test_rows_of_an_inert_cause_do_not_block_a_pass(equal, want):
    buckets = [("match", None, 5, 2), ("cube_only", "no-membership", 3, 1)]
    assert cells.verdict(equal, buckets, frozenset({"no-membership"})) == want


def test_rows_of_a_cause_that_is_not_inert_still_make_a_coincidental_match():
    buckets = [("match", None, 5, 2), ("cube_only", "late-entry", 3, 1)]
    assert cells.verdict(True, buckets, frozenset({"no-membership"})) == (
        cells.COINCIDENTAL
    )


def _swapped():
    """ADA by default; Chronic swaps to another view whose region member differs."""
    sm = _checks().sheets["ADA"]
    sheet = config.SheetMap(
        "ADA",
        "v",
        dims=sm.dims,
        measures={
            "ADA": config.MeasureMap("ADA", "avg_daily_attendance", param="Metric")
        },
        students="Students",
    )
    period = {"member": "p.period_type", "operator": "equals", "values": ["year"]}
    params = {
        "Metric": {
            "Chronic": config.ParamValue(
                cube_filters=(period,),
                measure="pct_chronically_absent",
                swaps_measure=True,
                view="p",
                rename={"regions_region_name": "region"},
            )
        }
    }
    cuts = (config.Cut("default"), config.Cut("chronic", params={"Metric": "Chronic"}))
    return _checks(sheets={"ADA": sheet}, params=params, cuts=cuts), period


def test_a_parameter_value_swaps_the_measure_view_and_renamed_members():
    checks, period = _swapped()
    cut = config.Cut("c", {"Region": "Camden"}, {"Metric": "Chronic"})
    q = cells.cube_query(checks, "ADA", cut, {})
    assert q["measures"] == ["p.count_students", "p.pct_chronically_absent"]
    assert q["dimensions"] == ["p.locations_abbreviation"]
    assert q["filters"] == [
        {"member": "p.region", "operator": "equals", "values": ["Camden"]},
        period,
    ]
    default = cells.cube_query(checks, "ADA", config.Cut("default"), {})
    assert default["measures"] == ["v.avg_daily_attendance", "v.count_students"]


def test_a_swapped_cut_is_judged_against_the_swapped_view(tmp_path):
    checks, _ = _swapped()
    exports = {
        ("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n",
        ("chronic", "ADA"): b"School,ADA,Students\nRise,50.0%,2\nLSP,0.0%,1\n",
    }
    answers = {
        **_ans(
            "default",
            [
                {"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
                {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"},
            ],
        ),
        cells.answer_key("chronic", "ADA"): {
            "data": [
                {"p.locations_abbreviation": "Rise", "p.pct_chronically_absent": "0.5"},
                {"p.locations_abbreviation": "LSP", "p.pct_chronically_absent": "0"},
            ],
            "last_refresh": "x",
            "sql": "s",
            "query": {},
        },
    }
    got = _judge(tmp_path, exports, answers, checks=checks)
    assert [(c.cut, c.verdict) for c in got] == [
        ("default", cells.PASS),
        ("default", cells.PASS),
        ("chronic", cells.PASS),
        ("chronic", cells.PASS),
    ]


def test_parse_format_reads_decimals_and_percent():
    assert cells.parse_format("p0.0%") == cells.Format(1, True)
    assert cells.parse_format("p0%") == cells.Format(0, True)
    assert cells.parse_format('n#,##0"%";-#,##0"%"') == cells.Format(0, False)
    assert cells.parse_format("n#,##0.00") == cells.Format(2, False)
    assert cells.parse_format(None) is None


@pytest.mark.parametrize(
    ("export", "cube", "want"),
    [
        ("0.965056526", 0.9670103, False),  # 96.5% shown vs 96.7%
        ("0.965056526", 0.9651, True),
        ("96.5%", 0.96549, True),
        ("97%", 0.9670103, None),  # the export is rounder than the dashboard
        ("0.0045", 0.0045, True),  # an exact half rounds up on both sides
    ],
)
def test_display_equal_at_the_dashboards_precision(export, cube, want):
    assert cells.display_equal(export, cube, 1.0, cells.Format(1, True)) is want


def test_a_cell_whose_export_is_rounder_than_the_dashboard_is_unproven(tmp_path):
    exports = {
        ("default", "ADA"): b"School,ADA,Students\nRise,94%,2\nLSP,90%,1\n",
        ("filter-region", "ADA"): b"School,ADA,Students\nLSP,0.900000000,1\n",
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
    pytest.importorskip("tableauhyperapi")
    # trunk-ignore(pyright/reportAttributeAccessIssue)
    from cube_validate import hyper

    with hyper.Workspace(tmp_path / "a.hyper", {}) as ws:
        _rows_table(ws)
        got = cells.judge(
            ws,
            _checks(),
            {"cuts": {}},
            answers,
            lambda cut, sheet: exports.get((cut, sheet)),
            {("ADA", "ADA"): "p0.0%"},
        )
    assert [(c.cut, c.verdict) for c in got] == [
        ("default", cells.UNPROVEN),
        ("default", cells.UNPROVEN),
        ("filter-region", cells.PASS),
    ]
    assert "1 decimal" in got[0].reason


def _null_measure():
    checks, _ = _swapped()
    params = {"Metric": {"HS Alt": config.ParamValue(measure=None, swaps_measure=True)}}
    cuts = (config.Cut("default"), config.Cut("alt", params={"Metric": "HS Alt"}))
    return replace(checks, params=params, cuts=cuts)


def test_a_null_measure_value_drops_the_default_member_from_the_query():
    checks = _null_measure()
    q = cells.cube_query(
        checks, "ADA", config.Cut("alt", params={"Metric": "HS Alt"}), {}
    )
    assert q["measures"] == ["v.count_students"]


def test_a_null_measure_cut_has_no_counterpart_for_its_measure(tmp_path):
    checks = _null_measure()
    exports = {
        ("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n",
        ("alt", "ADA"): b"School,ADA,Students\nRise,50.0%,2\nLSP,0.0%,1\n",
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
            "alt",
            [
                {"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
                {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"},
            ],
        ),
    }
    got = _judge(tmp_path, exports, answers, checks=checks)
    assert {c.verdict for c in got if c.cut == "alt"} == {cells.NO_COUNTERPART}


def test_shown_formats_like_the_dashboard():
    fmt = cells.Format(1, True)
    assert cells.shown("0.965056526", fmt) == "96.5%"
    assert cells.shown(0.965056526, fmt) == "96.5%"
    assert cells.shown(0.0045, fmt) == "0.5%"
    assert cells.shown("94.25%", fmt) == "94.3%"
    assert cells.shown(1204.0, cells.Format(0, False)) == "1204"
    assert cells.shown("0.965056526", None) == "0.965056526"
    assert cells.shown(None, fmt) == "None"
