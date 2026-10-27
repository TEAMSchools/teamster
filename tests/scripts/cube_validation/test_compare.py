import re

from cube_validation.compare import (
    Group,
    cell_verdict,
    clauses_for,
    groups_from,
    reconcile_sql,
    scope_filters,
)
from cube_validation.config import ColumnPair, Comparison, RowSpec

ROWS = RowSpec(
    grain=[
        ColumnPair("student_number", "lea_student_identifier"),
        ColumnPair("calendardate", "attendance_date"),
    ],
    values=[ColumnPair("is_present", "attendance_value")],
)
GROUP_BY = [ColumnPair("grade_level", "grade_level_cube")]


def _sql():
    return reconcile_sql(
        "SELECT 1 AS lea_student_identifier",
        "SELECT 1 AS student_number",
        ROWS,
        GROUP_BY,
    )


def _outer_select(sql: str) -> str:
    # The final SELECT list: from the last top-level SELECT to its FROM.
    tail = sql.rsplit("-- outer", 1)[1]
    return tail.split("FROM", 1)[0]


def test_reconcile_sql_returns_aggregates_only():
    outer = _outer_select(_sql())

    assert "n_rows" in outer
    assert "n_students" in outer
    assert "bucket" in outer
    assert "grade_level_cube" in outer
    for col in ("calendardate", "attendance_date", "is_present", "attendance_value"):
        assert col not in outer
    # Only the student (first grain pair) is counted, never selected raw.
    assert re.search(r"COUNT\(DISTINCT", outer)


def test_reconcile_sql_names_both_sources_and_buckets():
    sql = _sql()

    assert "SELECT 1 AS lea_student_identifier" in sql
    assert "SELECT 1 AS student_number" in sql
    for bucket in ("match", "value_differs", "dashboard_only", "cube_only"):
        assert f"'{bucket}'" in sql
    assert "FULL OUTER JOIN" in sql


def test_reconcile_sql_numbers_duplicates_on_the_grain():
    sql = _sql()

    assert sql.count("ROW_NUMBER() OVER (PARTITION BY") == 2
    assert "ORDER BY" in sql
    assert "__rn" in sql.split("FULL OUTER JOIN", 1)[1].split("-- outer")[0]


def test_reconcile_sql_values_compare_null_safe_and_type_tolerant():
    sql = _sql()

    assert (
        "SAFE_CAST(d.is_present AS FLOAT64) = SAFE_CAST(c.attendance_value AS FLOAT64)"
        in sql
    )
    assert "CAST(d.is_present AS STRING) = CAST(c.attendance_value AS STRING)" in sql
    assert "d.is_present IS NULL AND c.attendance_value IS NULL" in sql


def test_reconcile_sql_group_by_coalesces_cube_then_dashboard():
    sql = _sql()

    assert (
        "COALESCE(CAST(c.grade_level_cube AS STRING), CAST(d.grade_level AS STRING)) "
        "AS grade_level_cube"
    ) in sql


def test_reconcile_sql_group_by_column_is_selected_from_each_source():
    sql = reconcile_sql("SELECT 1", "SELECT 2", ROWS, GROUP_BY)

    assert "grade_level_cube" in sql
    assert "grade_level" in sql


def test_groups_from_drops_match_and_keeps_counts():
    rows = [
        {"bucket": "match", "grade_level_cube": "5", "n_rows": 90, "n_students": 9},
        {"bucket": "cube_only", "grade_level_cube": "5", "n_rows": 3, "n_students": 2},
        {
            "bucket": "value_differs",
            "grade_level_cube": None,
            "n_rows": 1,
            "n_students": 1,
        },
    ]

    assert groups_from("c1", rows) == [
        Group("c1", "grade_level_cube", "5", "cube_only", 3, 2),
        Group("c1", "grade_level_cube", "", "value_differs", 1, 1),
    ]


def test_groups_from_without_group_by_columns():
    rows = [{"bucket": "dashboard_only", "n_rows": 4, "n_students": 4}]

    assert groups_from("c1", rows) == [Group("c1", "", "", "dashboard_only", 4, 4)]


def test_cell_verdict_at_displayed_decimals():
    assert cell_verdict(0.9321, 0.9324, decimals=3) == "pass"
    assert cell_verdict(0.9321, 0.9372, decimals=3) == "differs"
    assert cell_verdict(None, 0.93, decimals=3) == "cube_only"
    assert cell_verdict(0.93, None, decimals=3) == "dashboard_only"
    assert cell_verdict(None, None, decimals=3) == "pass"


def test_clauses_for_finds_the_filter():
    sql = "select * from t where assessment_type != 'x' and y = 1"

    assert clauses_for(["assessment_type"], sql) == ["assessment_type != 'x'"]


def test_clauses_for_splits_on_top_level_and_only():
    sql = (
        "select * from t where (a = 1 and b = 2) and status in ('x', 'y')\n"
        "  and note = 'this and that'"
    )

    assert clauses_for(["a"], sql) == ["(a = 1 and b = 2)"]
    assert clauses_for(["note"], sql) == ["note = 'this and that'"]


def test_clauses_for_covers_qualify_having_and_join_on():
    sql = (
        "select * from a join b on a.k = b.k and b.flag = 1 "
        "where a.x > 2 qualify rn = 1 group by 1 having count(*) > flag_count"
    )

    assert clauses_for(["flag"], sql) == ["b.flag = 1"]
    assert clauses_for(["rn"], sql) == ["rn = 1"]
    assert clauses_for(["flag_count"], sql) == ["count(*) > flag_count"]
    assert clauses_for(["nothing"], sql) == []


def test_clauses_for_trims_to_one_line():
    sql = "select 1 from t where\n    x   =\n  1"

    assert clauses_for(["x"], sql) == ["x = 1"]


def test_scope_filter_from_comparison():
    comparison = Comparison(
        id="c",
        measure="m",
        scope=[{"cube": "v.grade_level", "values": ["5", "6"]}],
    )

    assert scope_filters(comparison) == [
        {"member": "v.grade_level", "operator": "equals", "values": ["5", "6"]}
    ]
    assert scope_filters(Comparison(id="c", measure="m")) == []
