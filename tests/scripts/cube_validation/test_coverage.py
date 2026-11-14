import dataclasses

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import coverage

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import Group, groups_from, reconcile_sql

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec

GRADE_5, GRADE_6 = '{"Grade": "5"}', '{"Grade": "6"}'
SPEC = Comparison(
    id="c1",
    measure="pct",
    dims=[ColumnPair("region_d", "region")],
    rows=RowSpec(
        grain=[ColumnPair("student", "student_number")],
        values=[ColumnPair("ok_d", "ok")],
    ),
    filters={"Grade": ColumnPair("grade_d", "grade")},
    cuts=[{"Grade": "5"}, {"Grade": "6"}],
)


def _cell(cut, region):
    return {"cut": cut, "dims": [["region", region]]}


def test_a_group_with_no_rows_under_the_cell_cut_does_not_cover_it():
    g = Group("c1", (("region", "Miami"),), "cube_only", 4, 4,
              cut_rows=((GRADE_5, 4, 0), (GRADE_6, 0, 0)))  # fmt: skip

    assert coverage.placed(_cell(GRADE_6, "Miami"), [g], SPEC) == []
    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) == [g]


def test_a_dims_differ_group_sits_in_both_its_cells():
    # Cube files the rows under Miami, the dashboard under Newark.
    g = Group(
        "c1",
        (("region", "Miami"), ("d:region", "Newark")),
        "dims_differ",
        2,
        2,
        cut_rows=((GRADE_5, 2, 2), (GRADE_6, 0, 0)),
    )

    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) == [g]
    assert coverage.placed(_cell(GRADE_5, "Newark"), [g], SPEC) == [g]
    assert coverage.placed(_cell(GRADE_5, "Paterson"), [g], SPEC) == []
    assert coverage.placed(_cell(GRADE_6, "Newark"), [g], SPEC) == []


def test_a_dims_differ_group_sits_in_a_side_s_cell_only_where_that_side_has_rows():
    # Under Grade 6 only the dashboard holds the rows: Newark's cell, not Miami's.
    g = Group(
        "c1",
        (("region", "Miami"), ("d:region", "Newark")),
        "dims_differ",
        2,
        2,
        cut_rows=((GRADE_5, 2, 0), (GRADE_6, 0, 2)),
    )

    assert coverage.placed(_cell(GRADE_6, "Miami"), [g], SPEC) == []
    assert coverage.placed(_cell(GRADE_6, "Newark"), [g], SPEC) == [g]


def test_a_dashboard_filtered_group_sits_in_cube_s_cell_only():
    # The dashboard's filter drops the rows: they show on Cube's side alone.
    g = Group(
        "c1",
        (("dashboard_filter", "future"), ("region", "Miami")),
        "dashboard_filtered",
        3,
        3,
        cut_rows=((GRADE_5, 3, 0), (GRADE_6, 0, 0)),
    )

    assert coverage.has_rows_in(g, _cell(GRADE_5, "Miami"))
    assert not coverage.has_rows_in(g, _cell(GRADE_5, "Newark"))
    assert not coverage.has_rows_in(g, _cell(GRADE_6, "Miami"))


def test_a_dashboard_only_group_counts_its_dashboard_rows():
    g = Group("c1", (("region", "Miami"),), "dashboard_only", 1, 1,
              cut_rows=((GRADE_5, 0, 1), (GRADE_6, 0, 0)))  # fmt: skip

    assert coverage.has_rows_in(g, _cell(GRADE_5, "Miami"))
    assert not coverage.has_rows_in(g, _cell(GRADE_6, "Miami"))


def test_cell_values_compare_by_cell_key():
    # A number the dashboard exports as 5.0 is the group's 5.
    spec = dataclasses.replace(SPEC, dims=[ColumnPair("grade_d", "grade")])
    g = Group("c1", (("grade", "5"),), "cube_only", 1, 1,
              cut_rows=(('{}', 1, 0),))  # fmt: skip

    assert coverage.placed({"cut": "{}", "dims": [["grade", "5.0"]]}, [g], spec) == [g]


def test_a_group_of_another_comparison_is_never_placed():
    g = Group("other", (("region", "Miami"),), "cube_only", 1, 1,
              cut_rows=((GRADE_5, 1, 0),))  # fmt: skip

    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) == []


def test_a_cell_on_a_grain_dim_stays_open_and_says_why():
    spec = dataclasses.replace(SPEC, dims=[ColumnPair("student", "student_number")])
    g = Group("c1", (), "cube_only", 1, 1, cut_rows=((GRADE_5, 1, 0),))
    cell = {"cut": GRADE_5, "dims": [["student_number", "101"]]}

    assert coverage.unplaceable(spec) == (
        "its dims student_number are part of the row grain"
    )
    assert coverage.placed(cell, [g], spec) is None
    assert coverage.unplaced(cell, [g], spec) == (
        "its dims student_number are part of the row grain"
    )


def test_a_comparison_without_rows_cannot_be_placed():
    spec = dataclasses.replace(SPEC, rows=None)

    assert coverage.unplaceable(spec) == "the comparison has no rows"
    assert coverage.placed(_cell(GRADE_5, "Miami"), [], spec) is None


def test_a_placeable_comparison_has_no_reason():
    assert coverage.unplaceable(SPEC) is None
    assert coverage.placed(_cell(GRADE_5, "Miami"), [], SPEC) == []


def test_a_cell_whose_groups_lack_rows_per_cut_cannot_be_placed():
    # A run saved before rows per cut were kept: no count is not 0 rows.
    g = Group("c1", (("region", "Miami"),), "cube_only", 4, 4)

    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) is None
    assert coverage.unplaced(_cell(GRADE_5, "Miami"), [g], SPEC) == (
        coverage.NOT_RECORDED
    )
    # A group no cell column agrees with is no candidate: the cell has no row.
    assert coverage.placed(_cell(GRADE_5, "Newark"), [g], SPEC) == []


def test_a_cell_dim_the_groups_do_not_split_by_cannot_be_placed():
    g = Group("c1", (("school", "X"),), "cube_only", 1, 1,
              cut_rows=((GRADE_5, 1, 0),))  # fmt: skip

    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) is None
    assert coverage.unplaced(_cell(GRADE_5, "Miami"), [g], SPEC) == (
        "its groups do not split by region"
    )


def test_a_row_both_sides_file_under_another_cut_is_a_group_in_both_cells(duck):
    # Student 1 matches; student 2 has the same value on both sides, but Cube
    # files it under Grade 5 and the dashboard under Grade 6.
    duck.table(
        "cube_t",
        "student_number BIGINT, grade VARCHAR, region VARCHAR, ok BOOLEAN",
        [(1, "5", "Miami", True), (2, "5", "Miami", True)],
    )
    duck.table(
        "dash_t",
        "student BIGINT, grade_d VARCHAR, region_d VARCHAR, ok_d BOOLEAN",
        [(1, "5", "Miami", True), (2, "6", "Miami", True)],
    )
    result = duck.rows(
        reconcile_sql(
            "SELECT * FROM `teamster-332318.m.cube_t`",
            "SELECT * FROM `teamster-332318.d.dash_t`",
            SPEC.rows,
            SPEC.dims,
            cuts=[("c.grade = '5'", "d.grade_d = '5'"),
                  ("c.grade = '6'", "d.grade_d = '6'")],
        )
    )  # fmt: skip

    (g,) = groups_from("c1", result, [GRADE_5, GRADE_6])
    assert g.bucket == "dims_differ" and g.n_rows == 1
    assert g.dims == (("region", "Miami"), ("d:region", "Miami"))
    assert g.cut_rows == ((GRADE_5, 1, 0), (GRADE_6, 0, 1))
    # Grade 5 has one row more on Cube's side, Grade 6 on the dashboard's.
    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) == [g]
    assert coverage.placed(_cell(GRADE_6, "Miami"), [g], SPEC) == [g]


def test_a_row_under_another_cut_is_a_group_with_no_group_by(duck):
    duck.table(
        "cube_t",
        "student_number BIGINT, grade VARCHAR, ok BOOLEAN",
        [(2, "5", True)],
    )
    duck.table(
        "dash_t", "student BIGINT, grade_d VARCHAR, ok_d BOOLEAN", [(2, "6", True)]
    )  # fmt: skip
    result = duck.rows(
        reconcile_sql(
            "SELECT * FROM `teamster-332318.m.cube_t`",
            "SELECT * FROM `teamster-332318.d.dash_t`",
            SPEC.rows,
            [],
            cuts=[("c.grade = '5'", "d.grade_d = '5'"),
                  ("c.grade = '6'", "d.grade_d = '6'")],
        )
    )  # fmt: skip

    (g,) = groups_from("c1", result, [GRADE_5, GRADE_6])
    assert g.bucket == "dims_differ" and g.dims == ()
    assert g.cut_rows == ((GRADE_5, 1, 0), (GRADE_6, 0, 1))
    spec = dataclasses.replace(SPEC, dims=[])
    assert coverage.placed({"cut": GRADE_6, "dims": []}, [g], spec) == [g]


def test_a_row_with_another_value_in_another_cell_sits_in_both_cells(duck):
    # Student 2's value differs too, and Cube files it under Miami, the
    # dashboard under Newark.
    duck.table(
        "cube_t",
        "student_number BIGINT, grade VARCHAR, region VARCHAR, ok BOOLEAN",
        [(2, "5", "Miami", True)],
    )
    duck.table(
        "dash_t",
        "student BIGINT, grade_d VARCHAR, region_d VARCHAR, ok_d BOOLEAN",
        [(2, "5", "Newark", False)],
    )
    result = duck.rows(
        reconcile_sql(
            "SELECT * FROM `teamster-332318.m.cube_t`",
            "SELECT * FROM `teamster-332318.d.dash_t`",
            SPEC.rows,
            SPEC.dims,
            cuts=[
                ("c.grade = '5'", "d.grade_d = '5'"),
                ("c.grade = '6'", "d.grade_d = '6'"),
            ],
        )
    )

    (g,) = groups_from("c1", result, [GRADE_5, GRADE_6])
    assert g.bucket == "value_differs"
    assert g.dims == (("region", "Miami"), ("d:region", "Newark"))
    assert coverage.placed(_cell(GRADE_5, "Miami"), [g], SPEC) == [g]
    assert coverage.placed(_cell(GRADE_5, "Newark"), [g], SPEC) == [g]


def test_a_row_with_another_value_in_the_same_cell_keeps_its_dims(duck):
    duck.table(
        "cube_t",
        "student_number BIGINT, grade VARCHAR, region VARCHAR, ok BOOLEAN",
        [(2, "5", "Miami", True)],
    )
    duck.table(
        "dash_t",
        "student BIGINT, grade_d VARCHAR, region_d VARCHAR, ok_d BOOLEAN",
        [(2, "5", "Miami", False)],
    )
    result = duck.rows(
        reconcile_sql(
            "SELECT * FROM `teamster-332318.m.cube_t`",
            "SELECT * FROM `teamster-332318.d.dash_t`",
            SPEC.rows,
            SPEC.dims,
            cuts=[("c.grade = '5'", "d.grade_d = '5'")],
        )
    )

    (g,) = groups_from("c1", result, [GRADE_5])
    assert g.bucket == "value_differs" and g.dims == (("region", "Miami"),)
