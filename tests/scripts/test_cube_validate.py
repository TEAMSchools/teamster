"""Tests for scripts/cube_validate.py. No live calls."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate.py"
FIX = Path(__file__).parent / "fixtures" / "cube_validate"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


cv = _load()


# ---------------------------------------------------------------- Task 1: grains
def test_parse_twb_keeps_only_sheets_on_named_dashboards():
    sheets = cv.parse_twb(FIX / "mini.twb", ["Live"])
    assert [s.name for s in sheets] == ["Tardy by School", "Headcount"]


def test_parse_twb_reads_shelves_filters_and_formulas():
    tardy = cv.parse_twb(FIX / "mini.twb", ["Live"])[0]
    assert tardy.dashboards == ["Live"]
    assert tardy.datasource == "rpt_demo (kipptaf_tableau)"
    assert tardy.measures == {"# Tardy": "IIF([att_code] = 'T', 1, 0)"}
    assert tardy.shelf_dims == ["region", "School", "calendardate@month"]
    assert tardy.filter_dims == ["gender"]
    assert tardy.other_filters == ["Region User Filter"]


def test_parse_twb_plain_column_measure_has_empty_formula():
    headcount = cv.parse_twb(FIX / "mini.twb", ["Live"])[1]
    assert headcount.measures == {"student_number": ""}


def test_propose_grains_adds_total_shelf_and_one_filter_at_a_time():
    sheets = cv.parse_twb(FIX / "mini.twb", ["Live"])
    assert cv.propose_grains(sheets, "# Tardy") == [
        [],
        ["region", "School", "calendardate@month"],
        ["region", "School", "calendardate@month", "gender"],
    ]


def test_grains_cli_prints_json(capsys):
    rc = cv.main(
        ["grains", str(FIX / "mini.twb"), "--dashboard", "Live", "--measure", "# Tardy"]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["measure"] == "# Tardy"
    assert [s["name"] for s in out["sheets"]] == ["Tardy by School"]
    assert out["grains"][0] == []


def test_parse_twb_reads_measures_shown_through_measure_values():
    (counts,) = cv.parse_twb(FIX / "mini.twb", ["Counts"])
    assert counts.measures == {"# Tardy": "IIF([att_code] = 'T', 1, 0)"}
    assert counts.shelf_dims == ["team"]
    assert counts.other_filters == []


# ---------------------------------------------------------------- Task 2: checks and queries
import datetime as dt  # noqa: E402

import pytest  # noqa: E402
import yaml  # noqa: E402

WINDOW = (dt.date(2026, 7, 1), dt.date(2026, 10, 7))


def _checks():
    return cv.load_checks(FIX / "checks.yml")


def _write_variant(tmp_path, mutate):
    data = yaml.safe_load((FIX / "checks.yml").read_text())
    mutate(data)
    p = tmp_path / "checks.yml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_load_checks_builds_dims_and_defaults():
    c = _checks()
    assert c["dimensions"]["month"] == cv.Dim(
        "month", "attendance_date", "date_trunc(calendardate, month)", "month"
    )
    assert c["dimensions"]["team"].cube is None
    assert c["scope_measure"] == "count_students"
    assert c["students_sql"] == "count(distinct student_number)"


def test_load_checks_rejects_unknown_grain_dim(tmp_path):
    p = _write_variant(tmp_path, lambda d: d["rows"][0]["grains"].append(["nope"]))
    with pytest.raises(cv.CheckError, match="unknown dimension"):
        cv.load_checks(p)


def test_load_checks_rejects_rate_without_den(tmp_path):
    p = _write_variant(tmp_path, lambda d: d["rows"][1]["metrics"][0].pop("den"))
    with pytest.raises(cv.CheckError, match="den"):
        cv.load_checks(p)


def test_load_checks_rejects_granularity_off_the_date_member(tmp_path):
    p = _write_variant(
        tmp_path, lambda d: d["dimensions"]["month"].update(cube="other_date")
    )
    with pytest.raises(cv.CheckError, match="date member"):
        cv.load_checks(p)


def test_load_checks_rejects_two_granular_dims_in_one_grain(tmp_path):
    def mutate(d):
        d["dimensions"]["week"] = {
            "cube": "attendance_date",
            "granularity": "week",
            "sql": "date_trunc(calendardate, week)",
        }
        d["rows"][1]["grains"].append(["month", "week"])

    with pytest.raises(cv.CheckError, match="one date part"):
        cv.load_checks(_write_variant(tmp_path, mutate))


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (dt.date(2026, 10, 8), (dt.date(2026, 7, 1), dt.date(2026, 10, 7))),
        (dt.date(2026, 7, 1), (dt.date(2025, 7, 1), dt.date(2026, 6, 30))),
        (dt.date(2027, 1, 15), (dt.date(2026, 7, 1), dt.date(2027, 1, 14))),
    ],
)
def test_academic_window_(today, expected):
    assert cv.academic_window(today) == expected


def test_cube_query_puts_date_part_on_the_time_dimension():
    c = _checks()
    q = cv.cube_query(
        "demo_view",
        ["avg_daily_attendance"],
        ["region", "month"],
        c["dimensions"],
        c["hard_filters"],
        WINDOW,
    )
    assert q == {
        "measures": ["demo_view.avg_daily_attendance"],
        "dimensions": ["demo_view.regions_region_name"],
        "timeDimensions": [
            {
                "dimension": "demo_view.attendance_date",
                "dateRange": ["2026-07-01", "2026-10-07"],
                "granularity": "month",
            }
        ],
        "filters": [
            {
                "member": "demo_view.regions_region_name",
                "operator": "equals",
                "values": ["Camden", "Newark"],
            }
        ],
        "limit": cv.CUBE_LIMIT,
        "timezone": "UTC",
    }
    assert cv.cube_key("demo_view", c["dimensions"]["month"]) == (
        "demo_view.attendance_date.month"
    )


def test_truth_sql_selects_aliases_and_groups_by_position():
    c = _checks()
    metrics = c["rows"][0]["metrics"] + c["rows"][1]["metrics"]
    sql = cv.truth_sql(
        "proj.ds.rpt_demo",
        metrics,
        ["region", "school"],
        c["dimensions"],
        c["hard_filters"],
        WINDOW,
        c["students_sql"],
    )
    assert sql == (
        "select region as g0, school_abbreviation as g1, sum(is_tardy) as m0, "
        "sum(is_present) as m1_num, sum(membershipvalue) as m1_den, "
        "count(distinct student_number) as n_students "
        "from `proj.ds.rpt_demo` "
        "where calendardate between '2026-07-01' and '2026-10-07' "
        "and region in ('Camden', 'Newark') "
        "group by 1, 2"
    )


def test_truth_sql_total_has_no_group_by():
    c = _checks()
    sql = cv.truth_sql(
        "t", c["rows"][0]["metrics"], [], c["dimensions"], [], WINDOW, "count(1)"
    )
    assert "group by" not in sql


# ---------------------------------------------------------------- Task 3: comparison
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "∅"),
        ("2026-09-01T00:00:00.000", "2026-09-01"),
        (dt.date(2026, 9, 1), "2026-09-01"),
        ("5", "5"),
        (5, "5"),
        (5.0, "5"),
        ("5.000", "5"),
        (True, "true"),
        ("False", "false"),
        (" Newark ", "Newark"),
    ],
)
def test_norm_key_(value, expected):
    assert cv.norm_key(value) == expected


def test_count_must_match_exactly():
    cells = cv.compare("count", {("A",): 10.0}, {("A",): (11.0, 50)})
    assert [c.ok for c in cells] == [False]
    assert cells[0].delta == 1.0


def test_count_missing_on_one_side_counts_as_zero():
    cells = cv.compare("count", {("A",): 0.0}, {})
    assert cells[0].ok


def test_count_cell_only_in_warehouse_fails():
    # The #5692 shape: the warehouse has rows Cube never returns.
    cells = cv.compare("count", {}, {("HS",): (40.0, 40)})
    assert not cells[0].ok
    assert cells[0].cube == 0.0


def test_rate_tolerance_boundary():
    ok, bad = cv.compare(
        "rate", {("A",): 0.901, ("B",): 0.9011}, {("A",): (0.9, 50), ("B",): (0.9, 50)}
    )
    assert ok.ok and not bad.ok


def test_rate_nulls():
    cells = cv.compare(
        "rate", {("A",): None, ("B",): 0.5}, {("A",): (None, 0), ("B",): (None, 0)}
    )
    assert [c.ok for c in cells] == [True, False]


def test_cube_and_truth_cells_join_on_normalized_keys():
    month = cv.Dim("month", "attendance_date", "x", "month")
    region = cv.Dim("region", "regions_region_name", "region")
    cube = cv.cube_cells(
        [
            {
                "v.regions_region_name": "Newark",
                "v.attendance_date.month": "2026-09-01T00:00:00.000",
                "v.avg_daily_attendance": "0.9",
            }
        ],
        "v",
        [region, month],
        "avg_daily_attendance",
    )
    truth = cv.truth_cells(
        [
            {
                "g0": "Newark",
                "g1": dt.date(2026, 9, 1),
                "m0_num": 9,
                "m0_den": 10,
                "n_students": 12,
            }
        ],
        2,
        0,
        "rate",
    )
    assert cube == {("Newark", "2026-09-01"): 0.9}
    assert truth == {("Newark", "2026-09-01"): (0.9, 12)}
    assert [c.ok for c in cv.compare("rate", cube, truth)] == [True]


def test_rate_with_zero_denominator_is_null():
    truth = cv.truth_cells([{"m0_num": 0, "m0_den": 0, "n_students": 3}], 0, 0, "rate")
    assert truth == {(): (None, 3)}


def test_cancelling_errors_fail_the_row():
    # Region total matches; two schools inside it are off in opposite directions.
    region = cv.summarize(
        cv.compare("count", {("N",): 20.0}, {("N",): (20.0, 200)}), "count"
    )
    school = cv.summarize(
        cv.compare(
            "count",
            {("N", "B"): 15.0, ("N", "C"): 5.0},
            {("N", "B"): (12.0, 120), ("N", "C"): (8.0, 80)},
        ),
        "count",
    )
    grains = [
        {"grain": ["region"], "status": "fail" if region["bad"] else "pass"},
        {"grain": ["region", "school"], "status": "fail" if school["bad"] else "pass"},
    ]
    assert region["bad"] == 0 and school["bad"] == 2
    assert cv.row_verdict(grains) == "fail"


def test_summarize_orders_worst_first_and_caps_at_five():
    cube = {(str(i),): float(i) for i in range(8)}
    truth = {(str(i),): (0.0, 50) for i in range(8)}
    s = cv.summarize(cv.compare("count", cube, truth), "count")
    assert s["cells"] == 8 and s["bad"] == 7
    assert [w["key"] for w in s["worst"]] == [["7"], ["6"], ["5"], ["4"], ["3"]]


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        (["pass", "pass"], "pass"),
        (["pass", "fail", "error"], "fail"),
        (["pass", "error"], "incomplete"),
        (["pass", "not_comparable"], "pass"),
        (["not_comparable"], "incomplete"),
    ],
)
def test_row_verdict(statuses, verdict):
    assert cv.row_verdict([{"status": s} for s in statuses]) == verdict


def test_rate_with_null_numerator_is_zero():
    truth = cv.truth_cells(
        [{"m0_num": None, "m0_den": 10, "n_students": 3}], 0, 0, "rate"
    )
    assert truth == {(): (0.0, 3)}
