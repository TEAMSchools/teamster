from __future__ import annotations

import pytest

from teamster.cube_sandbox import coverage

MANIFEST = {
    "cells": [
        {
            "kind": "null",
            "table": "dim_x",
            "column": "a",
            "detail": "",
            "status": "uncovered",
        },
        {
            "kind": "non_null",
            "table": "dim_x",
            "column": "a",
            "detail": "",
            "status": "uncovered",
        },
    ]
}


def test_a_covered_cell_reports_its_count() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": None}, {"a": "v"}]})
    assert all(c["observed"] > 0 for c in result)
    assert coverage.exit_code(result) == 0


def test_an_empty_table_fails_rather_than_passing_vacuously() -> None:
    # Zero rows means no cell was ever evaluated. Reporting that as covered is
    # the silent failure the manifest exists to prevent.
    result = coverage.assess(MANIFEST, {"dim_x": []})
    assert all(c["observed"] == 0 for c in result)
    assert coverage.exit_code(result) == 1


def test_a_table_missing_entirely_fails_rather_than_raising() -> None:
    # A generator that skipped a table is the same failure as one that wrote
    # it empty, and must not surface as a KeyError.
    result = coverage.assess(MANIFEST, {})
    assert all(c["observed"] == 0 for c in result)
    assert coverage.exit_code(result) == 1


def test_a_column_missing_from_every_row_is_not_counted_as_null() -> None:
    # `.get(column)` returns None for a column the generator never wrote at
    # all, which is indistinguishable from a written NULL. Counting the first
    # as covering the null cell lets a generator satisfy the contract by
    # omitting the column entirely — and then the non_null cell is the only
    # thing standing between that and a green run.
    result = coverage.assess(MANIFEST, {"dim_x": [{"b": 1}, {"b": 2}]})
    by_kind = {c["kind"]: c["observed"] for c in result}
    assert by_kind["null"] == 0
    assert by_kind["non_null"] == 0
    assert coverage.exit_code(result) == 1


def test_a_scope_cell_counts_matching_rows() -> None:
    manifest = {
        "cells": [
            {
                "kind": "scope",
                "table": "dim_staff_cube_access",
                "column": "staff_pii_scope",
                "detail": "all_in_scope",
                "status": "uncovered",
            }
        ]
    }
    result = coverage.assess(
        manifest,
        {
            "dim_staff_cube_access": [
                {"staff_pii_scope": "all_in_scope"},
                {"staff_pii_scope": "teaching_staff"},
            ]
        },
    )
    assert result[0]["observed"] == 1


def test_a_cell_with_no_table_is_reported_unproven_not_silently_zero() -> None:
    # derived / identity / divergence cells name no table, so row counting
    # cannot evaluate them. They must not be scored as covered, and the
    # report has to say they were never assessed rather than implying the
    # generator failed to produce them.
    manifest = {
        "cells": [
            {
                "kind": "derived",
                "table": None,
                "column": "hasRemit",
                "detail": "true",
                "status": "uncovered",
            }
        ]
    }
    result = coverage.assess(manifest, {})
    assert result[0]["observed"] == 0
    assert result[0]["status"] == "unproven"
    assert coverage.exit_code(result) == 1


def test_covered_cells_are_marked_covered() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": None}, {"a": "v"}]})
    assert {c["status"] for c in result} == {"covered"}


def test_uncovered_cells_are_listed_for_the_operator() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": "v"}]})
    assert coverage.uncovered(result) == [("null", "dim_x", "a", "")]
    assert coverage.exit_code(result) == 1


def test_an_unknown_cell_kind_is_rejected() -> None:
    # A new kind added to the manifest generator that coverage does not
    # understand must fail loudly; scoring it by the fall-through rule would
    # report a number that means nothing.
    manifest = {
        "cells": [
            {
                "kind": "invented",
                "table": "dim_x",
                "column": "a",
                "detail": "",
                "status": "uncovered",
            }
        ]
    }
    with pytest.raises(ValueError, match="unknown cell kind"):
        coverage.assess(manifest, {"dim_x": [{"a": 1}]})
