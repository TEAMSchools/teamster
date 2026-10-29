import re

from cube_validation.compare import (
    MANY,
    NONE,
    Group,
    cell_verdict,
    clauses_for,
    groups_from,
    reconcile_sql,
    scope_filters,
    trace_sql,
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
        "SAFE_CAST(CASE LOWER(CAST(d.is_present AS STRING)) WHEN 'true' THEN '1' "
        "WHEN 'false' THEN '0' ELSE CAST(d.is_present AS STRING) END AS FLOAT64) = "
        "SAFE_CAST(CASE LOWER(CAST(c.attendance_value AS STRING)) WHEN 'true' THEN '1' "
        "WHEN 'false' THEN '0' ELSE CAST(c.attendance_value AS STRING) END AS FLOAT64)"
        in sql
    )
    assert (
        "LOWER(CAST(d.is_present AS STRING)) = LOWER(CAST(c.attendance_value AS STRING))"
        in sql
    )
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
        Group("c1", (("grade_level_cube", "5"),), "cube_only", 3, 2),
        Group("c1", (("grade_level_cube", ""),), "value_differs", 1, 1),
    ]


def test_groups_from_without_group_by_columns():
    rows = [{"bucket": "dashboard_only", "n_rows": 4, "n_students": 4}]

    assert groups_from("c1", rows) == [Group("c1", (), "dashboard_only", 4, 4)]


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


def test_scope_filter_set_has_no_values_and_values_are_strings():
    comparison = Comparison(
        id="c",
        measure="m",
        scope=[
            {"cube": "v.membership_value", "operator": "equals", "values": [1]},
            {"cube": "v.attendance_value", "operator": "set"},
            {"cube": "v.is_in_session_day", "values": [True]},
        ],
    )

    assert scope_filters(comparison) == [
        {"member": "v.membership_value", "operator": "equals", "values": ["1"]},
        {"member": "v.attendance_value", "operator": "set"},
        {"member": "v.is_in_session_day", "operator": "equals", "values": ["true"]},
    ]


def test_cell_verdict_rounds_half_up_at_display_boundaries():
    assert cell_verdict(0.9325, 0.933, decimals=3) == "pass"
    assert cell_verdict(0.9335, 0.934, decimals=3) == "pass"
    assert cell_verdict(0.0005, 0.001, decimals=3) == "pass"
    assert cell_verdict(0.9325, 0.932, decimals=3) == "differs"


def test_reconcile_sql_grain_keys_join_across_numeric_types():
    sql = _sql()
    join = sql.split("FULL OUTER JOIN", 1)[1].split("-- outer")[0]

    key_c = "COALESCE(CAST(SAFE_CAST(CAST(c.lea_student_identifier AS STRING) AS FLOAT64) AS STRING), CAST(c.lea_student_identifier AS STRING))"
    key_d = "COALESCE(CAST(SAFE_CAST(CAST(d.student_number AS STRING) AS FLOAT64) AS STRING), CAST(d.student_number AS STRING))"
    assert f"\n    AND {key_c} = {key_d}" in join


def _null_safe(col: str) -> str:
    return f"IFNULL(CONCAT('=', COALESCE(CAST(SAFE_CAST(CAST({col} AS STRING)"


def _plain(col: str) -> str:
    return f"COALESCE(CAST(SAFE_CAST(CAST({col} AS STRING)"


def test_reconcile_sql_later_null_grain_matches_null_but_no_value():
    # A NULL keys as '' and any value, the empty string included, as '=<v>':
    # NULL meets NULL, never a value. Still an equality, so the join hashes.
    on = _sql().split("FULL OUTER JOIN", 1)[1].split("-- outer")[0].split("ON", 1)[1]
    for col in ("c.attendance_date", "d.calendardate"):
        assert _null_safe(col) in on
    assert " OR " not in on
    assert "IS NULL" not in on


def test_reconcile_sql_null_student_never_matches():
    # Rows with no student id would otherwise pair up by value order and read
    # as matches; a plain key leaves NULL = NULL unknown, so they stay one-sided.
    on = _sql().split("FULL OUTER JOIN", 1)[1].split("-- outer")[0].split("ON", 1)[1]
    for col in ("c.lea_student_identifier", "d.student_number"):
        assert _plain(col) in on
        assert _null_safe(col) not in on


def test_reconcile_sql_numbers_duplicates_on_the_join_keys():
    # Each side partitions by the keys it joins on, so NULLs and 1 vs 1.0
    # number alike on both sides.
    sql = _sql()
    c_part = sql.split("c AS (", 1)[1].split("d AS (", 1)[0]
    d_part = sql.split("d AS (", 1)[1].split("joined AS (", 1)[0]
    for part, student, later in (
        (c_part, "lea_student_identifier", "attendance_date"),
        (d_part, "student_number", "calendardate"),
    ):
        partition = part.split("PARTITION BY", 1)[1].split("ORDER BY", 1)[0]
        assert partition.startswith(f" {_plain(student)}")
        assert _null_safe(student) not in partition
        assert _null_safe(later) in partition


def test_groups_from_keeps_one_group_per_two_dim_row():
    rows = [
        {
            "bucket": "value_differs",
            "regions_region_name": "Camden",
            "grade_level": 2,
            "n_rows": 7,
            "n_students": 5,
        }
    ]
    assert groups_from("c1", rows) == [
        Group(
            "c1",
            (("regions_region_name", "Camden"), ("grade_level", "2")),
            "value_differs",
            7,
            5,
        )
    ]


def test_scope_filter_comparison_operators_use_cube_names():
    comparison = Comparison(
        id="c",
        measure="m",
        scope=[
            {"cube": "v.membership_value", "operator": "gt", "values": [0]},
            {"cube": "v.attendance_code", "operator": "not_equals", "values": ["TD"]},
        ],
    )

    assert scope_filters(comparison) == [
        {"member": "v.membership_value", "operator": "gt", "values": ["0"]},
        {"member": "v.attendance_code", "operator": "notEquals", "values": ["TD"]},
    ]


def test_cell_verdict_ignores_float_noise_at_a_half_way_tie():
    # BigQuery AVG gives 15/16 as 0.9374999999999999; the sheet shows 0.938.
    assert cell_verdict(0.9375, 0.9374999999999999, decimals=3) == "pass"
    assert cell_verdict(0.9375, 0.9374, decimals=3) == "differs"


FILTERED_ROWS = RowSpec(
    grain=[ColumnPair(dashboard="student_number", cube="lea_student_identifier")],
    values=[ColumnPair(dashboard="att_code", cube="attendance_code")],
)


def test_reconcile_counts_rows_a_dashboard_only_filter_drops_apart():
    sql = reconcile_sql(
        "SELECT 1", "SELECT 2", FILTERED_ROWS, [], filters=[("__df0", "enroll_status")]
    )
    assert "THEN 'dashboard_filtered'" in sql
    assert "WHEN NOT d.__df0 THEN 'enroll_status'" in sql
    assert "AS __filter" in sql and "GROUP BY bucket, __filter" in sql


def test_reconcile_without_filters_has_no_filter_column():
    assert "__filter" not in reconcile_sql("SELECT 1", "SELECT 2", FILTERED_ROWS, [])


def test_groups_from_names_the_dropping_filter_only_on_its_rows():
    rows = [
        {"bucket": "dashboard_filtered", "__filter": "enroll_status", "grade_level": 9,
         "n_rows": 50, "n_students": 3},
        {"bucket": "cube_only", "__filter": None, "grade_level": 9,
         "n_rows": 2, "n_students": 1},
    ]  # fmt: skip
    assert groups_from("c1", rows) == [
        Group("c1", (("dashboard_filter", "enroll_status"), ("grade_level", "9")),
              "dashboard_filtered", 50, 3),
        Group("c1", (("grade_level", "9"),), "cube_only", 2, 1),
    ]  # fmt: skip


# --- trace_sql -----------------------------------------------------------------


def _trace(**kw):
    args = dict(
        bucket="cube_only",
        side="dashboard",
        variants=[("dashboard:main:1", "SELECT 1 AS student_number")],
    )
    args.update(kw)
    return trace_sql(
        "SELECT 1 AS lea_student_identifier",
        "SELECT 1 AS student_number",
        ROWS,
        GROUP_BY,
        **args,
    )


def test_trace_sql_returns_group_columns_a_step_and_a_count_only():
    for combine in (True, False):
        outer = _trace(combine=combine).rsplit("-- outer", 1)[1]

        select = outer.split("FROM", 1)[0]
        assert (
            select == "\nSELECT bucket, grade_level_cube, step_id, COUNT(*) AS n_rows\n"
        )
        for col in ("calendardate", "attendance_date", "student_number"):
            assert col not in outer
            assert "lea_student_identifier" not in outer


def test_trace_sql_rebuilds_the_bucket_inside_the_query():
    sql = _trace()

    assert "FULL OUTER JOIN d" in sql
    assert "FROM joined WHERE bucket = 'cube_only'" in sql
    # Each variant is keyed the way the reconcile keys the grain.
    assert "COALESCE(CAST(SAFE_CAST(CAST(student_number AS STRING)" in sql
    assert "v0.__n >= p.__rn" in sql
    assert "'dashboard:main:1' AS step_id" in sql


def test_trace_sql_names_the_side_s_grain_columns():
    sql = _trace(side="cube", bucket="dashboard_only")

    assert "CAST(lea_student_identifier AS STRING)" in sql.split("v0 AS", 1)[1]
    assert "bucket = 'dashboard_only'" in sql


def test_trace_sql_leaves_out_rows_a_shallower_level_explained():
    sql = _trace(exclude=["SELECT 2 AS student_number"])

    assert "x0 AS (" in sql
    assert "NOT EXISTS (SELECT 1 FROM x0 WHERE" in sql


def test_trace_sql_counts_each_row_once_when_combined():
    combined = _trace(combine=True)
    apart = _trace(combine=False)

    assert "COUNT(DISTINCT step_id) = 1" in combined
    assert f"ELSE '{MANY}'" in combined and f"'{NONE}'" in combined
    assert "per_row" not in apart and f"'{NONE}' AS step_id FROM p" in apart
