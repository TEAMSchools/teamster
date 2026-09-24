from __future__ import annotations

from pathlib import Path

from teamster.cube_sandbox import model

CUBE_ROOT = Path(__file__).parents[2] / "src" / "cube"


def test_table_set_includes_the_cube_js_only_table() -> None:
    tables = model.table_set(CUBE_ROOT)
    # dim_staff_reporting_chain appears in no cube YAML; cube.js reads it
    # directly. Missing it fails identity resolution for reporting_chain
    # personas only, which is silent.
    assert "dim_staff_reporting_chain" in tables
    # Every entry is a bare table name, not a qualified path.
    assert all("." not in t for t in tables)


def test_referenced_columns_are_keyed_by_table() -> None:
    columns = model.referenced_columns(CUBE_ROOT)
    assert "dim_students" in columns
    assert columns["dim_students"], "a cube with dimensions yields columns"
    # Keys are a subset of the table set: a column cannot be referenced on a
    # table the model never reads.
    assert set(columns) <= model.table_set(CUBE_ROOT)


def test_policy_columns_are_flat_names() -> None:
    cols = model.policy_columns(CUBE_ROOT)
    # row_level filters name a flat view member, never a cube-qualified path.
    assert cols and all("." not in c for c in cols)


def test_policy_columns_descends_into_or_and_and_blocks() -> None:
    cols = model.policy_columns(CUBE_ROOT)
    # staff_pii.yml's staff-pii-reporting_chain_or_below_rank policy nests its
    # filters under `or: [{and: [...]}, {member: staff_key, ...}]`. A
    # top-level-only read of `row_level.filters[].member` never sees inside
    # that nesting, so job_function_level goes missing — and a later task
    # that exempts policy columns from a null-value rule would then write a
    # null into it, silently breaking that persona's row_level filter.
    assert "job_function_level" in cols


def test_scope_values_come_from_access_js() -> None:
    values = model.scope_values(CUBE_ROOT / "access.js")
    assert "staff_pii_scope" in values
    assert "all_in_scope" in values["staff_pii_scope"]
    assert "none" not in values["staff_pii_scope"], "none is the absence of a group"
    # The four real staff_pii_scope values (the case labels of
    # `switch (row.staff_pii_scope)`), and none of the case labels belonging
    # to access.js's OTHER switch statements
    # (computeAllowedAbbreviations's network/region/school,
    # computeAllowedDepartmentGroups's all/own_group). A bare `case "..."`
    # regex with no block boundary sweeps those in too — they are not, and
    # never were, staff_pii_scope values, and a manifest cell generated for
    # one is a cell no policy can ever satisfy.
    assert values["staff_pii_scope"] == {
        "all_in_scope",
        "teaching_staff",
        "reporting_chain",
        "reporting_chain_or_below_rank",
    }
    for spurious in ("all", "own_group", "region", "school", "network"):
        assert spurious not in values["staff_pii_scope"]
    # student_location_scope's values are interpolated into a template literal
    # (`student-${row.student_location_scope}`) in access.js, not enumerated as
    # string literals, so they are not statically extractable by regex. A prior
    # regex-based attempt silently returned an empty set here, which downstream
    # would reject every valid student-location persona declaration. All three
    # values access.js's buildGroups branches on for this scope must be present.
    assert values["student_location_scope"] == {"region", "school", "network"}
