from datetime import datetime, timedelta, timezone

from cube_validation.answers import HandCheck, example_cell, hand_check
from cube_validation.config import ColumnPair, Comparison, ViewConfig
from cube_validation.decisions import Applied
from cube_validation.moment import Build
from cube_validation.report import RunResult

START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 27, 6, 5, tzinfo=timezone.utc)
DIMS = [["regions_region_name", "Newark"], ["grade_level", "7"]]


def _cell(key="a", dashboard=10.0, cube=12.0, n=30, dims=DIMS):
    return {
        "comparison": "enrollment",
        "cut": "All",
        "key": key,
        "dims": dims,
        "dashboard": dashboard,
        "cube": cube,
        "n_students": n,
    }


def _run(cells):
    return RunResult(
        view="enrollment",
        moment=Build(start=START, end=END, job_id="j"),
        measures=[],
        applied=Applied(),
        diff_cells=cells,
        cell_sql={"enrollment": {"All": ["SELECT 1 AS d", "SELECT 2 AS c"]}},
        cell_sql_usd={"enrollment": {"All": [0.01, 0.02]}},
    )


def _cfg(dashboard_region="regions_region_name"):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[
            ColumnPair(dashboard_region, "regions_region_name"),
            ColumnPair("grade_level", "grade_level"),
        ],
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def test_example_cell_is_biggest_difference_with_reviewed_dims_only():
    run = _run([_cell("a", 10, 12), _cell("b", 10, 20), _cell("c", 10, 15)])

    assert example_cell(run, "enrollment")["key"] == "b"


def test_example_cell_ties_go_to_the_lowest_key():
    run = _run([_cell("b", 10, 20), _cell("a", 10, 20)])

    assert example_cell(run, "enrollment")["key"] == "a"


def test_example_cell_skips_cells_under_10_students():
    run = _run([_cell("small", 10, 99, n=9), _cell("none", 10, 98, n=None)])
    assert example_cell(run, "enrollment") is None

    run = _run([_cell("small", 10, 99, n=9), _cell("ok", 10, 12, n=10)])
    assert example_cell(run, "enrollment")["key"] == "ok"


def test_example_cell_skips_a_teacher_or_student_dim():
    run = _run([_cell(dims=[["teacher_name", "x"]])])

    assert example_cell(run, "enrollment") is None


def test_no_example_cell_returns_none():
    run = _run([])

    assert example_cell(run, "enrollment") is None
    assert hand_check(run, _cfg(), "enrollment", START) is None


def test_hand_check_sql_filters_to_the_example_cell():
    check = hand_check(_run([_cell()]), _cfg(), "enrollment", START)

    assert isinstance(check, HandCheck)
    want = "WHERE regions_region_name = 'Newark' AND grade_level = '7'"
    assert check.dashboard_sql == f"SELECT * FROM (SELECT 1 AS d) {want}"
    assert check.cube_sql == f"SELECT * FROM (SELECT 2 AS c) {want}"
    assert (check.dashboard, check.cube) == (10.0, 12.0)
    assert (check.dashboard_usd, check.cube_usd) == (0.01, 0.02)


def test_hand_check_filters_the_dashboard_side_by_its_own_column_names():
    check = hand_check(_run([_cell()]), _cfg("Region"), "enrollment", START)

    assert check.dashboard_sql.endswith("WHERE Region = 'Newark' AND grade_level = '7'")
    assert check.cube_sql.endswith(
        "WHERE regions_region_name = 'Newark' AND grade_level = '7'"
    )


def test_hand_checks_expire_after_7_days():
    run = _run([_cell()])
    expires = START + timedelta(days=7)

    before = hand_check(run, _cfg(), "enrollment", expires - timedelta(seconds=1))
    at = hand_check(run, _cfg(), "enrollment", expires)

    assert before.expires == expires and not before.expired
    assert at.expired
