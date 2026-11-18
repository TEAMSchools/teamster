import json
from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, compare, formula, pipeline, report

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo, utc_literal

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
    # The guard is defensive: the reconcile never matches a NULL student, and
    # `test_key_sql_is_null_for_a_null_student` pins the NULL key itself.
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


def test_matched_keys_leave_out_a_saved_dashboard_only_key_the_rebuild_misses(duck):
    # Saved while the dashboard alone held 2; Cube now holds it too, so the
    # rebuilt join files 2 `match` and only the saved dashboard rows leave it out.
    _tables(duck, [(1, "a", 1, "X")], [(1, "a", 1, "X"), (2, "a", 1, "X")])
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
    # The key over `__k*` and over the saved rows' own grain is one string,
    # else no saved key would ever leave a matched key out. The dashboard
    # alone holds 1, so the join files it unmatched and the run saves it.
    _tables(duck, [], [(1, "a", 1, "X")])
    sql = formula.matched_ctes(CFG, COMPARISON, VALUED, SAVED)
    _save(duck)
    (other,) = duck.rows(f"{sql}\nSELECT __key FROM __other")
    saved = duck.rows(
        f"SELECT {formula.key_sql(['__gd0', '__gd1'], [False, False])} AS k "
        "FROM saved_t"
    )
    assert other["__key"] is not None
    assert [r["k"] for r in saved] == [other["__key"]]


# --- the dashboard side -------------------------------------------------------

SIDE = Comparison(
    id="mastery",
    measure="pct",
    dashboard_view="d.dash_t",
    sheet_query="AVG(score)",
    dims=[ColumnPair("school", "abbreviation")],
    rows=RowSpec(
        grain=[ColumnPair("student", "lea"), ColumnPair("item", "aid")],
        values=[ColumnPair("score", "score_c")],
    ),
)
BUILD = Build(
    datetime(2026, 10, 28, 21, 34, tzinfo=timezone.utc),
    datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc),
    "job",
)
D1, D2 = date(2026, 10, 1), date(2026, 10, 2)


class _Catalog:
    """Every relation a plain table, so `as_of` only pins it to the moment."""

    def table(self, dataset, name):
        return TableInfo("TABLE", None)


def _side_tables(duck, dash_rows, cube_rows):
    """Dashboard rows (student, item, score, school, region, in_scope,
    updated) and Cube rows (lea, aid, score_c, abbreviation, region_c)."""
    duck.table(
        "dash_t",
        "student BIGINT, item VARCHAR, score DOUBLE, school VARCHAR, "
        "region VARCHAR, in_scope BOOLEAN, updated DATE",
        dash_rows,
    )
    duck.table(
        "cube_t",
        "lea BIGINT, aid VARCHAR, score_c DOUBLE, abbreviation VARCHAR, "
        "region_c VARCHAR",
        cube_rows,
    )


def _side_sides(cfg, comparison) -> pipeline.RowSides:
    """The row SQL `compare` reconciles for `comparison`, over the toy tables."""
    columns = pipeline.unique(p.cube for p in pipeline.row_pairs(comparison))
    cube = (
        "SELECT "
        + ", ".join(f"{c} AS `v__{c}`" for c in columns)
        + " FROM `teamster-332318.m.cube_t` AS c"
    )
    dash = pipeline.dashboard_rows_sql(cfg, comparison)
    return pipeline.RowSides(
        cube=AsOf(cube, frozenset(), frozenset()),
        dashboard=AsOf(dash, frozenset(), frozenset()),
        cube_rows_sql=cube,
        columns=columns,
    )


def _recomputed(duck, comparison=SIDE) -> dict[tuple[str, str], float]:
    """The dashboard side on matched rows, as `sort` runs it, by (cut, school)."""
    cfg = replace(CFG, comparisons=[comparison])
    sides = _side_sides(cfg, comparison)
    _save(duck, cfg, sides)
    body = formula.dashboard_side_sql(
        cfg,
        comparison,
        pipeline.comparison_cuts(comparison),
        BUILD,
        _Catalog(),
        keep=True,
    )
    ctes = formula.matched_ctes(cfg, comparison, sides, SAVED)
    rows = duck.rows(f"{ctes}\nSELECT * FROM (\n{body}\n)")
    return {(r["__cut"], r["school"]): r["value"] for r in rows}


def _sheet(duck, comparison, cut) -> float:
    """The run's own cell: the sheet query over every dashboard row."""
    cfg = replace(CFG, comparisons=[comparison])
    (row,) = duck.rows(pipeline.sheet_query(cfg, comparison, cut))
    return row["value"]


def test_dashboard_side_recomputes_a_cell_on_matched_rows_only(duck):
    # 1 and 2 match; the dashboard alone holds 3 and Cube alone holds 4.
    _side_tables(
        duck,
        [(1, "a", 0.5, "X", "N", True, D1), (2, "a", 1.0, "X", "N", True, D1),
         (3, "a", 0.0, "X", "N", True, D1)],
        [(1, "a", 0.5, "X", "N"), (2, "a", 1.0, "X", "N"), (4, "a", 0.0, "X", "N")],
    )  # fmt: skip

    assert _sheet(duck, SIDE, {}) == 0.5
    assert _recomputed(duck) == {("{}", "X"): 0.75}


def test_dashboard_side_keeps_only_the_latest_row_under_reduce(duck):
    # The reconcile sees 1's latest row only; the older one never matched.
    comparison = replace(
        SIDE, rows=replace(SIDE.rows, reduce={"rule": "latest", "by": "updated"})
    )
    _side_tables(
        duck,
        [(1, "a", 0.0, "X", "N", True, D1), (1, "a", 1.0, "X", "N", True, D2),
         (2, "a", 0.5, "X", "N", True, D2)],
        [(1, "a", 1.0, "X", "N"), (2, "a", 0.5, "X", "N")],
    )  # fmt: skip

    assert _sheet(duck, comparison, {}) == 0.5
    assert _recomputed(duck, comparison) == {("{}", "X"): 0.75}


def test_dashboard_side_leaves_out_rows_outside_dashboard_scope(duck):
    # 1's out-of-scope row shares its key with the in-scope row that matched.
    comparison = replace(
        SIDE,
        rows=replace(
            SIDE.rows,
            dashboard_scope=[
                {"dashboard": "in_scope", "operator": "equals", "values": [True]}
            ],
        ),
    )
    _side_tables(
        duck,
        [(1, "a", 1.0, "X", "N", True, D1), (1, "a", 0.0, "X", "N", False, D1),
         (2, "a", 0.5, "X", "N", True, D1)],
        [(1, "a", 1.0, "X", "N"), (2, "a", 0.5, "X", "N")],
    )  # fmt: skip

    assert _sheet(duck, comparison, {}) == 0.5
    assert _recomputed(duck, comparison) == {("{}", "X"): 0.75}


REGION = replace(
    SIDE,
    filters={"Region": ColumnPair("region", "region_c")},
    cuts=[{}, {"Region": "Miami"}],
)


def test_dashboard_side_tags_each_cut(duck):
    # The dashboard alone holds 3, in Miami, so both cuts leave it out.
    _side_tables(
        duck,
        [(1, "a", 1.0, "X", "Miami", True, D1), (2, "a", 0.5, "X", "N", True, D1),
         (3, "a", 0.0, "X", "Miami", True, D1)],
        [(1, "a", 1.0, "X", "Miami"), (2, "a", 0.5, "X", "N")],
    )  # fmt: skip

    assert _sheet(duck, REGION, {"Region": "Miami"}) == 0.5
    assert _recomputed(duck, REGION) == {
        ("{}", "X"): 0.75,
        ('{"Region": "Miami"}', "X"): 1.0,
    }


def test_dashboard_self_check_reproduces_the_sheet_query(duck):
    comparison = replace(
        REGION,
        dims=[ColumnPair("school", "abbreviation"), ColumnPair("region", "region_c")],
        dashboard_filters=[
            {"dashboard": "in_scope", "operator": "equals", "values": [True]}
        ],
    )
    cfg = replace(CFG, comparisons=[comparison])
    _side_tables(
        duck,
        [(1, "a", 1.0, "X", "Miami", True, D1), (2, "a", 0.5, "X", "N", True, D1),
         (3, "a", 0.0, "Y", "Miami", True, D1), (4, "a", 0.2, "X", "N", False, D1)],
        [],
    )  # fmt: skip
    cuts = pipeline.comparison_cuts(comparison)

    sql = formula.dashboard_side_sql(
        cfg, comparison, cuts, BUILD, _Catalog(), keep=False
    )

    def rows(found):
        return sorted((r["__cut"], r["school"], r["region"], r["value"]) for r in found)

    expected = [
        {"__cut": pipeline.cut_label(cut), **r}
        for cut in cuts
        for r in duck.rows(pipeline.sheet_query(cfg, comparison, cut))
    ]
    assert f"FOR SYSTEM_TIME AS OF TIMESTAMP '{utc_literal(BUILD.start)}'" in sql
    assert len(expected) == 5
    assert rows(duck.rows(sql)) == rows(expected)
