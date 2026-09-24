from __future__ import annotations

from teamster.cube_sandbox import snapshot


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
