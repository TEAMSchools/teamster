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
from cube_validation.timetravel import AsOf, TableInfo, as_of, utc_literal

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


def test_matched_ctes_refuse_a_comparison_with_no_rows():
    comparison = replace(COMPARISON, rows=None)

    with pytest.raises(pipeline.Refusal, match="has no rows"):
        formula.matched_ctes(
            replace(CFG, comparisons=[comparison]), comparison, VALUED, SAVED
        )


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


def _recomputed(duck, comparison=SIDE, cfg=CFG) -> dict[tuple[str, str], float]:
    """The dashboard side on matched rows, as `sort` runs it, by (cut, school)."""
    cfg = replace(cfg, comparisons=[comparison])
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


def test_dashboard_side_leaves_out_a_key_with_two_latest_rows(duck):
    # 1's two rows tie as the latest, so the reconcile sees both: it matches
    # one and files the other an unmatched duplicate, and the dashboard side
    # reads neither.
    comparison = replace(
        SIDE, rows=replace(SIDE.rows, reduce={"rule": "latest", "by": "updated"})
    )
    _side_tables(
        duck,
        [(1, "a", 1.0, "X", "N", True, D2), (1, "a", 1.0, "X", "N", True, D2),
         (2, "a", 0.25, "X", "N", True, D2)],
        [(1, "a", 1.0, "X", "N"), (2, "a", 0.25, "X", "N")],
    )  # fmt: skip

    assert _recomputed(duck, comparison) == {("{}", "X"): 0.25}


# A daily grain: `day` is a TIMESTAMP on both sides and the view's time
# dimension, so the reconcile keys it by its DATE.
DAILY = replace(
    SIDE,
    rows=RowSpec(
        grain=[ColumnPair("student", "lea"), ColumnPair("day", "day_c")],
        values=[ColumnPair("score", "score_c")],
    ),
)
DAILY_CFG = replace(CFG, time_dimension="day_c")
T1 = datetime(2026, 10, 1, 8, 30)


def _daily_tables(duck, dash_rows, cube_rows):
    """Dashboard rows (student, day, score, school) and Cube rows (lea, day_c,
    score_c, abbreviation), `day` a TIMESTAMP on both."""
    duck.table(
        "dash_t", "student BIGINT, day TIMESTAMP, score DOUBLE, school VARCHAR",
        dash_rows,
    )  # fmt: skip
    duck.table(
        "cube_t",
        "lea BIGINT, day_c TIMESTAMP, score_c DOUBLE, abbreviation VARCHAR",
        cube_rows,
    )


def test_dashboard_side_keys_a_timestamp_grain_as_a_date(duck):
    # 1 and 2 match; the dashboard alone holds 3 and Cube alone holds 4.
    _daily_tables(
        duck,
        [(1, T1, 0.5, "X"), (2, T1, 1.0, "X"), (3, T1, 0.0, "X")],
        [(1, T1, 0.5, "X"), (2, T1, 1.0, "X"), (4, T1, 0.0, "X")],
    )

    assert _recomputed(duck, DAILY, DAILY_CFG) == {("{}", "X"): 0.75}


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


# --- the Cube side ------------------------------------------------------------


def test_fact_grain_maps_each_member_to_its_fact_column():
    sql = (
        "SELECT `f`.student_number `v__student`, `f`.item_id `v__item` "
        "FROM kipptaf_marts.fct_x AS `f`"
    )

    assert formula.fact_grain(sql, "v", ["student", "item"]) == (
        "kipptaf_marts.fct_x",
        ["student_number", "item_id"],
    )


def test_fact_grain_refuses_an_expression():
    sql = (
        "SELECT CAST(`f`.a AS STRING) `v__student`, `f`.item_id `v__item` "
        "FROM kipptaf_marts.fct_x AS `f`"
    )

    with pytest.raises(
        formula.NotCompared, match="grain column student is an expression"
    ):
        formula.fact_grain(sql, "v", ["student", "item"])


def test_fact_grain_refuses_a_subquery_alias():
    sql = (
        "SELECT `s`.student_number `v__student`, `s`.item_id `v__item` "
        "FROM (SELECT * FROM kipptaf_marts.fct_x) AS `s`"
    )

    with pytest.raises(
        formula.NotCompared, match="grain column student is an expression"
    ):
        formula.fact_grain(sql, "v", ["student", "item"])


def test_fact_grain_refuses_grain_columns_on_two_tables():
    sql = (
        "SELECT `f`.student_number `v__student`, `g`.item_id `v__item` "
        "FROM kipptaf_marts.fct_x AS `f` "
        "LEFT JOIN kipptaf_marts.fct_y AS `g` ON `g`.k = `f`.k"
    )

    with pytest.raises(formula.NotCompared, match="more than one table"):
        formula.fact_grain(sql, "v", ["student", "item"])


def test_fact_grain_refuses_sql_it_cannot_parse():
    with pytest.raises(formula.NotCompared, match="Cube's SQL could not be parsed"):
        formula.fact_grain("SELECT `f.a FROM (", "v", ["student"])


def test_cube_read_tables_are_the_fact_and_the_also_facts_cube_reads():
    cfg = replace(
        CFG,
        fact="kipptaf_marts.fct_x",
        also_facts=["kipptaf_marts.fct_goals", "kipptaf_marts.fct_other"],
    )
    sql = (
        "SELECT 1 FROM kipptaf_marts.fct_x AS `f` "
        "LEFT JOIN KIPPTAF_MARTS.fct_goals AS `g` ON TRUE"
    )

    assert formula.cube_read_tables(cfg, sql) == [
        "kipptaf_marts.fct_x",
        "kipptaf_marts.fct_goals",
    ]


def test_filtered_tables_skips_a_goals_lookup():
    cols = {"m.fct": {"student_number", "item_id"}, "m.fct_goals": {"school", "grade"}}
    assert formula.filtered_tables(
        ["m.fct", "m.fct_goals"], ["student_number", "item_id"], cols.__getitem__
    ) == ["m.fct"]

    with pytest.raises(formula.NotCompared, match="no table Cube reads carries"):
        formula.filtered_tables(["m.fct_goals"], ["student_number"], cols.__getitem__)


END, START = utc_literal(BUILD.end), utc_literal(BUILD.start)
# Cube's SQL as `as_of` leaves it: the fact read twice, at two moments, and a
# goals lookup.
PINNED = (
    f"SELECT `f`.lea `v__lea` FROM `teamster-332318.m.fct` AS `f` "
    f"FOR SYSTEM_TIME AS OF TIMESTAMP '{END}'\n"
    "LEFT JOIN `teamster-332318.m.fct_goals` AS `g` "
    f"FOR SYSTEM_TIME AS OF TIMESTAMP '{END}' ON TRUE\n"
    "WHERE `f`.k IN (SELECT k FROM `teamster-332318.m.fct` AS `f2` "
    f"FOR SYSTEM_TIME AS OF TIMESTAMP '{START}')"
)


def test_rewrite_wraps_every_reference_of_each_table():
    def wrapped(alias, at, predicate):
        return (
            f"(SELECT * FROM `teamster-332318.m.fct` "
            f"FOR SYSTEM_TIME AS OF TIMESTAMP '{at}' WHERE {predicate}) AS `{alias}`"
        )

    def expected(predicate):
        return PINNED.replace(
            f"`teamster-332318.m.fct` AS `f` FOR SYSTEM_TIME AS OF TIMESTAMP '{END}'",
            wrapped("f", END, predicate),
        ).replace(
            f"`teamster-332318.m.fct` AS `f2` "
            f"FOR SYSTEM_TIME AS OF TIMESTAMP '{START}'",
            wrapped("f2", START, predicate),
        )

    key = formula.key_sql(["lea", "day"], [False, True])
    kept = formula.rewrite_cube_sql(
        PINNED, ["m.fct"], ["lea", "day"], [False, True], keep=True
    )
    whole = formula.rewrite_cube_sql(
        PINNED, ["m.fct"], ["lea", "day"], [False, True], keep=False
    )

    assert kept == expected(f"{key} IN (SELECT __key FROM __matched)")
    assert whole == expected("TRUE")
    assert "`teamster-332318.m.fct_goals` AS `g`" in kept


def test_rewrite_refuses_a_reference_with_no_alias():
    bare = PINNED.replace(" AS `f2`", "")

    with pytest.raises(
        formula.NotCompared, match="Cube's SQL reads m.fct with no alias"
    ):
        formula.rewrite_cube_sql(bare, ["m.fct"], ["lea"], [False], keep=True)
    with pytest.raises(formula.NotCompared, match="Cube's SQL does not read m.other"):
        formula.rewrite_cube_sql(PINNED, ["m.other"], ["lea"], [False], keep=True)


class _Ex:
    """`pipeline.Expand` over a toy Cube: `AVG(score_c)` from `cube_t` by the
    query's dims, under its equals filters, expanded as of a moment."""

    def cube_sql(self, query, rows=False):
        dims = [m.split(".", 1)[1] for m in query["dimensions"]]
        where = " AND ".join(
            f"`c`.{f['member'].split('.', 1)[1]} = {pipeline.lit(f['values'][0])}"
            for f in query["filters"]
        )
        select = ", ".join(
            [*(f"`c`.{d} `v__{d}`" for d in dims), "AVG(`c`.score_c) `v__pct`"]
        )
        group = ", ".join(str(i + 1) for i in range(len(dims)))
        return f"SELECT {select} FROM m.cube_t AS `c` WHERE {where or 'TRUE'}" + (
            f" GROUP BY {group}" if group else ""
        )

    def at(self, sql, ts):
        return as_of(sql, ts, _Catalog())


def _cube_cells(duck, comparison=SIDE, cfg=CFG, *, keep=True, shared=frozenset()):
    """The Cube side as `sort` runs it, by (cut, school), and its SQL; the
    dashboard's row SQL reads `shared`."""
    cfg = replace(cfg, comparisons=[comparison])
    sides = _side_sides(cfg, comparison)
    sides = replace(sides, dashboard=replace(sides.dashboard, tables=shared))
    _save(duck, cfg, sides)
    body = formula.cube_side_sql(
        cfg,
        comparison,
        pipeline.comparison_cuts(comparison),
        BUILD,
        ex=_Ex(),
        sides=sides,
        tables=["m.cube_t"],
        columns=[p.cube for p in comparison.rows.grain],
        keep=keep,
    )
    sql = body
    if keep:
        ctes = formula.matched_ctes(cfg, comparison, sides, SAVED)
        sql = f"{ctes}\nSELECT * FROM (\n{body}\n)"
    cells = {(r["__cut"], r["abbreviation"]): r["value"] for r in duck.rows(sql)}
    return cells, body


def test_cube_side_recomputes_on_matched_rows_and_self_checks(duck):
    # 1 and 2 match; the dashboard alone holds 3 and Cube alone holds 4.
    _side_tables(
        duck,
        [(1, "a", 0.5, "X", "Miami", True, D1), (2, "a", 1.0, "X", "N", True, D1),
         (3, "a", 0.0, "X", "Miami", True, D1)],
        [(1, "a", 0.5, "X", "Miami"), (2, "a", 1.0, "X", "N"),
         (4, "a", 0.0, "X", "Miami")],
    )  # fmt: skip
    miami = '{"Region": "Miami"}'
    ex = _Ex()
    run = {
        (pipeline.cut_label(cut), r["abbreviation"]): r["value"]
        for cut in pipeline.comparison_cuts(REGION)
        for r in duck.rows(
            pipeline.wrap_cube(
                ex.at(
                    ex.cube_sql(pipeline.cell_query("v", REGION, cut)), BUILD.end
                ).sql,
                "v",
                ["abbreviation"],
                set(),
                "pct",
            )
        )
    }

    kept, sql = _cube_cells(duck, REGION)
    whole, _ = _cube_cells(duck, REGION, keep=False)
    _, shared = _cube_cells(duck, REGION, shared=frozenset({"m.cube_t"}))

    assert run == {("{}", "X"): 0.5, (miami, "X"): 0.25}
    assert whole == run
    assert kept == {("{}", "X"): 0.75, (miami, "X"): 0.5}
    assert f"TIMESTAMP '{END}'" in sql
    # A table the dashboard's rows also read is read at the build start.
    assert f"TIMESTAMP '{START}'" in shared and END not in shared


def test_cube_side_keys_a_timestamp_grain_as_a_date(duck):
    # 1 and 2 match; the dashboard alone holds 3 and Cube alone holds 4.
    _daily_tables(
        duck,
        [(1, T1, 0.5, "X"), (2, T1, 1.0, "X"), (3, T1, 0.0, "X")],
        [(1, T1, 0.5, "X"), (2, T1, 1.0, "X"), (4, T1, 0.0, "X")],
    )

    kept, _ = _cube_cells(duck, DAILY, DAILY_CFG)

    assert kept == {("{}", "X"): 0.75}
