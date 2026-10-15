"""Rows layer with planted gaps: each plant has an exact expected bucket count."""

import datetime as dt

import pytest

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import config, hyper, rows  # noqa: E402

D = [dt.date(2026, 10, 5), dt.date(2026, 10, 6), dt.date(2026, 10, 7)]
STUDENTS = {101: "Rise", 102: "Rise", 103: "TEAM", 104: "TEAM"}
TAB_COLS = [
    ("student_number", "bigint"),
    ("calendardate", "date"),
    ("school_abbreviation", "text"),
    ("region", "text"),
    ("is_absent", "double"),
]
CUB_COLS = [
    ("lea_student_identifier", "double"),
    ("attendance_date", "date"),
    ("locations_abbreviation", "text"),
    ("regions_region_name", "text"),
    ("is_absent", "double"),
    ("membership_value", "double"),
]


def _tab_rows():
    return [(s, d, sc, "Newark", 0.0) for s, sc in STUDENTS.items() for d in D]


def _cub_rows():
    return [
        (float(s), d, sc, "Newark", 0.0, 1.0) for s, sc in STUDENTS.items() for d in D
    ]


def _checks(causes=()):
    return config.Checks(
        dashboard="d",
        workbook="w",
        workbook_luid="l",
        review_project_luid="p",
        dashboards=("Overview",),
        datasource="ds",
        dashboard_table="p.d.t",
        period_start=D[0],
        window=config.Window(
            dt.time(15, 30), dt.time(6), dt.time(15), "America/New_York"
        ),
        cost_cap_gb=50,
        quiet_minutes=(0, 10),
        cube=config.CubeRows("v", "attendance_date", ()),
        key=(
            config.Expr(
                "student",
                "student_number",
                'cast("{p}lea_student_identifier" as bigint)',
            ),
            config.Expr("day", "calendardate", "attendance_date"),
            config.Expr("school", "school_abbreviation", "locations_abbreviation"),
        ),
        compare=(config.Expr("is_absent", "is_absent", "is_absent"),),
        labels=(config.Expr("region", "region", "regions_region_name"),),
        student_key="student",
        date_key="day",
        scope_key="school",
        causes=tuple(causes),
        filters={},
        params={},
        sheets={},
        cuts=(config.Cut("default"),),
        excluded_sheets={},
    )


def _run(tmp_path, tab, cub, checks=None, scope=("Rise", "TEAM"), period=None):
    hyper.write_table(tmp_path / "e.hyper", "Extract", "Extract", TAB_COLS, tab)
    hyper.write_table(tmp_path / "c.hyper", "cube", "rows", CUB_COLS, cub)
    with hyper.Workspace(
        tmp_path / "a.hyper", {"tab": tmp_path / "e.hyper", "cub": tmp_path / "c.hyper"}
    ) as ws:
        res = rows.build(
            ws, checks or _checks(), None if scope is None else list(scope), period
        )
        by = {}
        for b in res.buckets:
            by[(b["base"], b["cause"])] = by.get((b["base"], b["cause"]), 0) + b["rows"]
        return res, by


def test_clean_sides_all_match(tmp_path):
    res, by = _run(tmp_path, _tab_rows(), _cub_rows())
    assert by == {("match", None): 12}
    assert all(res.invariants.values())


def test_school_day_deleted_from_cube_is_dashboard_only(tmp_path):
    cub = [r for r in _cub_rows() if not (r[2] == "Rise" and r[1] == D[1])]
    res, by = _run(tmp_path, _tab_rows(), cub)
    assert by == {("match", None): 10, ("dashboard_only", "unexplained"): 2}
    assert all(res.invariants.values())


def test_flipped_absences_are_value_differs_on_that_column(tmp_path):
    cub = [(*r[:4], 1.0 if r[0] == 101.0 else r[4], r[5]) for r in _cub_rows()]
    res, by = _run(tmp_path, _tab_rows(), cub)
    assert by[("value_differs", "unexplained")] == 3
    assert res.differing_columns == {"is_absent": 3}


def test_moved_school_is_one_dashboard_only_and_one_cube_only(tmp_path):
    cub = [
        (r[0], r[1], "TEAM" if (r[0] == 101.0 and r[1] == D[0]) else r[2], *r[3:])
        for r in _cub_rows()
    ]
    _, by = _run(tmp_path, _tab_rows(), cub)
    assert (
        by[("dashboard_only", "unexplained")] == 1
        and by[("cube_only", "unexplained")] == 1
    )


def test_duplicate_dashboard_row_is_dashboard_only_and_claimable(tmp_path):
    tab = _tab_rows() + [(101, D[0], "Rise", "Newark", 0.0)]
    cause = config.Cause("dup", "duplicate dashboard row", "t__dup > 1", "dashboard")
    res, by = _run(tmp_path, tab, _cub_rows(), _checks([cause]))
    assert by[("dashboard_only", "dup")] == 1 and res.totals["tableau"] == 13
    assert all(res.invariants.values())


def test_school_outside_cube_scope(tmp_path):
    tab = _tab_rows() + [(105, D[0], "Hatch", "Newark", 0.0)]
    _, by = _run(tmp_path, tab, _cub_rows())
    assert by[("outside_scope", "outside_scope")] == 1


def test_empty_scope_puts_every_dashboard_only_row_outside_scope(tmp_path):
    tab = _tab_rows() + [(105, D[0], "Hatch", "Newark", 0.0)]
    _, by = _run(tmp_path, tab, _cub_rows(), scope=())
    assert not [k for k in by if k[0] == "dashboard_only"]
    assert by[("outside_scope", "outside_scope")] >= 1


def test_no_scope_means_no_scope_check(tmp_path):
    tab = _tab_rows() + [(105, D[0], "Hatch", "Newark", 0.0)]
    _, by = _run(tmp_path, tab, _cub_rows(), scope=None)
    assert by[("dashboard_only", "unexplained")] >= 1
    assert not [k for k in by if k[0] == "outside_scope"]


def test_cause_claims_only_its_rows(tmp_path):
    cub = _cub_rows() + [(101.0, dt.date(2026, 10, 10), "Rise", "Newark", None, 0.0)]
    cause = config.Cause(
        "break",
        "break day",
        "base = 'cube_only' and c_membership_value = 0",
        "dashboard",
    )
    _, by = _run(tmp_path, _tab_rows(), cub, _checks([cause]))
    assert by[("cube_only", "break")] == 1 and by[("match", None)] == 12


def test_overlapping_causes_are_a_tool_error(tmp_path):
    cub = [r for r in _cub_rows() if r[1] != D[2]]
    a = config.Cause("a", "a", "base = 'dashboard_only'", "cube")
    b = config.Cause("b", "b", "k_day = '2026-10-07'", "cube")
    with pytest.raises(rows.RowsError, match="a, b"):
        _run(tmp_path, _tab_rows(), cub, _checks([a, b]))


def test_buckets_carry_labels_month_and_students(tmp_path):
    res, _ = _run(tmp_path, _tab_rows(), _cub_rows())
    (b,) = res.buckets
    assert b["region"] == "Newark" and b["month"] == dt.date(2026, 10, 1)
    assert b["students"] == 4 and res.totals == {
        "tableau": 12,
        "cube": 12,
        "joined": 12,
    }


def test_duplicates_pair_by_value_so_reruns_agree(tmp_path):
    tab = _tab_rows() + [(101, D[0], "Rise", "Newark", 1.0)]
    runs = []
    for name in ("one", "two"):
        sub = tmp_path / name
        sub.mkdir()
        res, by = _run(sub, tab, _cub_rows())
        runs.append(res.buckets)
    assert by == {("match", None): 12, ("dashboard_only", "unexplained"): 1}
    assert runs[0] == runs[1]


def test_last_year_extract_row_is_outside_the_period_not_dashboard_only(tmp_path):
    tab = _tab_rows() + [(101, dt.date(2025, 10, 6), "Rise", "Newark", 0.0)]
    res, by = _run(tmp_path, tab, _cub_rows(), period=(D[0], D[2]))
    assert by == {("match", None): 12, ("outside_period", "outside_period"): 1}
    assert all(res.invariants.values())


def test_outside_period_wins_over_outside_scope_and_is_unclaimable(tmp_path):
    tab = _tab_rows() + [(105, dt.date(2025, 10, 6), "Hatch", "Newark", 0.0)]
    cause = config.Cause("any", "claims anything", "true", "cube")
    res, by = _run(tmp_path, tab, _cub_rows(), _checks([cause]), period=(D[0], D[2]))
    assert by == {("match", None): 12, ("outside_period", "outside_period"): 1}
    assert all(res.invariants.values())
