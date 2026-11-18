import json
from dataclasses import replace

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, compare, formula, report

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec, ViewConfig

from .test_explain import SIDES


@pytest.fixture(autouse=True)
def _cache_in_tmp(monkeypatch, tmp_path):
    """Keep every test off the analyst's own cache and spend ledger."""
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setattr(report, "CACHE_ROOT", tmp_path / "cache")


# --- matched keys -------------------------------------------------------------

ROWS = RowSpec(
    grain=[ColumnPair("student", "lea"), ColumnPair("item", "aid")],
    values=[ColumnPair("score", "score_c")],
)
COMPARISON = Comparison(
    id="mastery",
    measure="pct",
    dims=[ColumnPair("school", "abbreviation")],
    rows=ROWS,
)
CFG = ViewConfig(view="v", fact="m.fct", comparisons=[COMPARISON])
CUBE = (
    "SELECT lea AS `v__lea`, aid AS `v__aid`, score_c AS `v__score_c`, "
    "abbreviation AS `v__abbreviation` FROM `teamster-332318.m.cube_t` AS c"
)
VALUED = replace(
    SIDES,
    cube_rows_sql=CUBE,
    columns=["lea", "aid", "score_c", "abbreviation"],
    dashboard=replace(
        SIDES.dashboard,
        sql="SELECT student, item, score, school FROM `teamster-332318.d.dash_t`",
    ),
)
SAVED = "`teamster-332318`.`cube_validation_scratch`.`saved_t`"


def _tables(duck, cube_rows, dash_rows, dash_columns=""):
    duck.table(
        "cube_t",
        "lea BIGINT, aid VARCHAR, score_c BIGINT, abbreviation VARCHAR",
        cube_rows,
    )
    duck.table(
        "dash_t",
        "student BIGINT, item VARCHAR, score BIGINT, school VARCHAR" + dash_columns,
        dash_rows,
    )


def _save(duck, cfg=CFG, sides=VALUED):
    """What `compare` leaves behind: the comparison's saved unmatched rows."""
    duck.rows("DROP TABLE IF EXISTS __joined")
    for statement in compare.save_script(cfg, cfg.comparisons[0], sides, SAVED, None):
        duck.rows(statement)


def _matched(duck, cfg=CFG, sides=VALUED) -> list[int]:
    """The students `__matched` holds, one per key, sorted; a NULL key fails."""
    sql = formula.matched_ctes(cfg, cfg.comparisons[0], sides, SAVED)
    keys = [r["__key"] for r in duck.rows(f"{sql}\nSELECT __key FROM __matched")]
    return sorted(int(float(json.loads(k)["k0"])) for k in keys)


def test_matched_keys_leave_out_every_unmatched_and_one_sided_key(duck):
    # 1 matches; Cube alone holds 2; 3's value differs; the dashboard holds 4 twice.
    _tables(
        duck,
        [(1, "a", 10, "X"), (2, "a", 10, "X"), (3, "a", 10, "X"), (4, "a", 10, "X")],
        [(1, "a", 10, "X"), (3, "a", 99, "X"), (4, "a", 10, "X"), (4, "a", 10, "X")],
    )
    _save(duck)

    assert _matched(duck) == [1]


def test_matched_keys_leave_out_a_key_with_any_unmatched_duplicate(duck):
    # Saved while 5 matched once; then each side gains a 2nd copy of 5 that
    # differs, so only the rebuilt join, not the saved rows, holds it unmatched.
    _tables(duck, [(1, "a", 1, "X"), (5, "a", 1, "X")],
            [(1, "a", 1, "X"), (5, "a", 1, "X")])  # fmt: skip
    _save(duck)
    _tables(duck, [(1, "a", 1, "X"), (5, "a", 1, "X"), (5, "a", 2, "X")],
            [(1, "a", 1, "X"), (5, "a", 1, "X"), (5, "a", 3, "X")])  # fmt: skip

    assert _matched(duck) == [1]


def test_matched_keys_never_hold_a_null_student(duck):
    _tables(duck, [(None, "a", 1, "X"), (1, "a", 1, "X")],
            [(None, "a", 1, "X"), (1, "a", 1, "X")])  # fmt: skip
    _save(duck)

    assert _matched(duck) == [1]


def test_matched_keys_leave_out_rows_a_dashboard_filter_drops(duck):
    # The dashboard drops 2, which Cube keeps (`dashboard_filtered`, never
    # saved), and 3, which Cube lacks (filed `match` with no Cube row).
    comparison = replace(
        COMPARISON,
        dashboard_filters=[
            {"dashboard": "future", "operator": "equals", "values": ["no"]}
        ],
    )
    cfg = replace(CFG, comparisons=[comparison])
    sides = replace(
        VALUED,
        dashboard=replace(
            VALUED.dashboard,
            sql="SELECT student, item, score, school, __df0 "
            "FROM `teamster-332318.d.dash_t`",
        ),
    )
    _tables(
        duck,
        [(1, "a", 1, "X"), (2, "a", 1, "X")],
        [(1, "a", 1, "X", True), (2, "a", 1, "X", False), (3, "a", 1, "X", False)],
        ", __df0 BOOLEAN",
    )
    _save(duck, cfg, sides)

    assert _matched(duck, cfg, sides) == [1]


def test_matched_keys_leave_out_a_saved_unmatched_key_the_rebuild_misses(duck):
    # Saved while Cube alone held 2; the dashboard now holds it too, so the
    # rebuilt join files 2 `match` and only the saved rows leave it out.
    _tables(duck, [(1, "a", 1, "X"), (2, "a", 1, "X")], [(1, "a", 1, "X")])
    _save(duck)
    _tables(duck, [(1, "a", 1, "X"), (2, "a", 1, "X")],
            [(1, "a", 1, "X"), (2, "a", 1, "X")])  # fmt: skip

    assert _matched(duck) == [1]


def test_key_sql_reads_a_timestamp_and_its_date_alike(duck):
    assert duck.rows(
        f"SELECT {formula.key_sql(['t'], [True])} = "
        f"{formula.key_sql(['d'], [False])} AS same "
        "FROM (SELECT TIMESTAMP '2026-01-05 00:00:00' AS t, DATE '2026-01-05' AS d)"
    )[0]["same"]


def test_key_sql_is_null_for_a_null_student(duck):
    assert (
        duck.rows(f"SELECT {formula.key_sql(['s', 'i'], [False, False])} AS k "
                  "FROM (SELECT CAST(NULL AS INT64) AS s, 'a' AS i)")[0]["k"]
        is None
    )  # fmt: skip


def test_matched_keys_key_alike_on_the_rebuilt_join_and_the_saved_rows(duck):
    # The key over `__k*` and over a side's own grain is one string, else no
    # saved key would ever leave a matched key out.
    _tables(duck, [(1, "a", 1, "X")], [(1, "a", 1, "X")])
    sql = formula.matched_ctes(CFG, COMPARISON, VALUED, SAVED)
    _save(duck)
    (match,) = duck.rows(f"{sql}\nSELECT __key FROM __match")
    saved = duck.rows(
        f"SELECT {formula.key_sql(['__gd0', '__gd1'], [False, False])} AS k "
        f"FROM (SELECT student AS __gd0, item AS __gd1 FROM dash_t)"
    )
    assert [r["k"] for r in saved] == [match["__key"]]
