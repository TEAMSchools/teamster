"""Hyper write and attach. Needs tableauhyperapi (uv run --with)."""

import datetime as dt

import pytest

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import hyper  # noqa: E402


def test_write_then_join_two_files(tmp_path):
    a, b = tmp_path / "a.hyper", tmp_path / "b.hyper"
    hyper.write_table(
        a,
        "Extract",
        "Extract",
        [("k", "bigint"), ("d", "date")],
        [(1, dt.date(2026, 10, 6)), (2, dt.date(2026, 10, 7))],
    )
    n = hyper.write_table(
        b, "cube", "rows", [("k", "bigint"), ("v", "text")], [(2, "x"), (3, None)]
    )
    assert n == 2
    with hyper.Workspace(tmp_path / "work.hyper", {"tab": a, "cub": b}) as ws:
        got = ws.dicts(
            'select coalesce(t.k, c.k) as k, t.d, c.v from "tab"."Extract"."Extract" t '
            'full outer join "cub"."cube"."rows" c on t.k = c.k order by 1'
        )
        assert got == [
            {"k": 1, "d": dt.date(2026, 10, 6), "v": None},
            {"k": 2, "d": dt.date(2026, 10, 7), "v": "x"},
            {"k": 3, "d": None, "v": None},
        ]
        assert ws.columns("cub", "cube", "rows") == ["k", "v"]
        ws.execute('create temporary table t2 as select * from "cub"."cube"."rows"')
        assert ws.count("t2 where v is null") == 1
