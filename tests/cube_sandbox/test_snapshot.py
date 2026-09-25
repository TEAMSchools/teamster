from __future__ import annotations

import pytest

from teamster.cube_sandbox import snapshot


def test_check_missing_tables_raises_and_names_the_gap() -> None:
    # A table the model asked for (dim_c) never came back in the query
    # result — exercises the guard that protects against a snapshot that
    # writes successfully while silently missing a table.
    with pytest.raises(SystemExit) as excinfo:
        snapshot.check_missing_tables(
            requested={"dim_a", "dim_b", "dim_c"}, found={"dim_a", "dim_b"}
        )
    assert "dim_c" in str(excinfo.value)


def test_check_missing_tables_passes_when_nothing_missing() -> None:
    snapshot.check_missing_tables(
        requested={"dim_a", "dim_b"}, found={"dim_a", "dim_b"}
    )


def test_render_is_sorted_and_stable() -> None:
    rows = [
        {
            "table_name": "dim_b",
            "column_name": "z",
            "data_type": "STRING",
            "is_nullable": "YES",
        },
        {
            "table_name": "dim_a",
            "column_name": "a",
            "data_type": "INT64",
            "is_nullable": "NO",
        },
    ]
    out = snapshot.render(rows)
    # Sorted output is what makes the committed diff readable, which is the
    # whole point of committing it.
    assert list(out["tables"]) == ["dim_a", "dim_b"]
    assert out["tables"]["dim_a"]["a"] == {"type": "INT64", "nullable": False}
    assert out["tables"]["dim_b"]["z"]["nullable"] is True
