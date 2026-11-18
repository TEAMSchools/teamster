import json
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, compare, formula, latest, pipeline, report, results

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import JOB_ID, CostCapError

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.cube_client import CubeRefusal

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.reconcile import Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.saved import labels, table_id, table_sql

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo, as_of, utc_literal

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.trace import TIMEOUT_S, Prepared
from google.api_core.exceptions import BadRequest
from google.auth.exceptions import RefreshError

from .test_explain import SIDES, Wh


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


THROUGH_ROWS = (
    "SELECT school, AVG(score) AS value FROM ({rows}) WHERE {where} GROUP BY school"
)


@pytest.mark.parametrize(
    "template",
    [
        # No `{rows}`: the view itself, every row.
        "SELECT school, AVG(score) AS value "
        "FROM `teamster-332318`.`d`.`dash_t` WHERE {where} GROUP BY school",
        # `{rows}`, and the view read again beside it.
        "SELECT school, AVG(score) AS value FROM ({rows}) WHERE {where} AND student "
        "IN (SELECT student FROM `teamster-332318`.`d`.`dash_t`) GROUP BY school",
    ],
)
def test_dashboard_side_refuses_a_template_that_reads_rows_outside_rows(template):
    # Cube's side reads matched rows only, so a dashboard side that reads
    # every row would file a row difference as a formula difference.
    comparison = replace(SIDE, sheet_query=None, sheet_query_sql=template)

    with pytest.raises(
        formula.NotCompared,
        match=r"its sheet_query_sql does not read every row through \{rows\}",
    ):
        formula.dashboard_side_sql(
            replace(CFG, comparisons=[comparison]), comparison, [{}], BUILD,
            _Catalog(), keep=True,
        )  # fmt: skip


def test_dashboard_side_reads_a_template_through_rows_on_matched_rows(duck):
    comparison = replace(SIDE, sheet_query=None, sheet_query_sql=THROUGH_ROWS)
    _side_tables(
        duck,
        [(1, "a", 0.5, "X", "N", True, D1), (2, "a", 1.0, "X", "N", True, D1),
         (3, "a", 0.0, "X", "N", True, D1)],
        [(1, "a", 0.5, "X", "N"), (2, "a", 1.0, "X", "N"), (4, "a", 0.0, "X", "N")],
    )  # fmt: skip

    assert _recomputed(duck, comparison) == {("{}", "X"): 0.75}


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


def test_rewrite_wraps_a_bare_alias_as_it_wraps_an_as_alias():
    # `as_of` keeps a dbt reference's alias as written, with no `AS`.
    bare = PINNED.replace(" AS `f2`", " f2")

    sql = formula.rewrite_cube_sql(bare, ["m.fct"], ["lea"], [False], keep=False)

    assert sql.count("`teamster-332318.m.fct`") == 2
    assert (
        f"(SELECT * FROM `teamster-332318.m.fct` FOR SYSTEM_TIME AS OF TIMESTAMP "
        f"'{END}' WHERE TRUE) AS `f`"
    ) in sql
    assert (
        f"(SELECT * FROM `teamster-332318.m.fct` FOR SYSTEM_TIME AS OF TIMESTAMP "
        f"'{START}' WHERE TRUE) f2"
    ) in sql


def test_rewrite_refuses_a_reference_it_cannot_place():
    # The second read of the fact has no moment, so the pattern misses it.
    unplaced = PINNED + "\nJOIN `teamster-332318.m.fct` AS `f3` ON TRUE"

    with pytest.raises(
        formula.NotCompared,
        match="Cube's SQL reads m.fct in a form the rewrite does not know",
    ):
        formula.rewrite_cube_sql(unplaced, ["m.fct"], ["lea"], [False], keep=True)


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


# --- verdicts -----------------------------------------------------------------

MIAMI = '{"Region": "Miami"}'
DECIMALS = replace(COMPARISON, decimals=2)


def _cell(cut="{}", school="X", dashboard=0.6, cube=0.5):
    """A differing cell as `run.diff_cells` holds it."""
    return {
        "comparison": "mastery",
        "cut": cut,
        "key": f"abbreviation={school}",
        "dims": [["abbreviation", school]],
        "dashboard": dashboard,
        "cube": cube,
        "n_students": None,
        "kind": "cells",
    }


def _dash(cut, school, value):
    return {"__cut": cut, "school": school, "value": value}


def _cube(cut, school, value):
    return {"__cut": cut, "abbreviation": school, "value": value}


def _verdicts(cells, dash, cube, dash_self=None, cube_self=None):
    """`verdicts` whose self-checks reproduce the run's cells unless given."""
    whole_dash = [_dash(c["cut"], c["dims"][0][1], c["dashboard"]) for c in cells]
    whole_cube = [_cube(c["cut"], c["dims"][0][1], c["cube"]) for c in cells]
    return formula.verdicts(
        DECIMALS,
        "fp",
        cells,
        dash,
        cube,
        whole_dash if dash_self is None else dash_self,
        whole_cube if cube_self is None else cube_self,
    )


def test_verdicts_file_a_cell_that_still_differs_as_formula():
    check = _verdicts([_cell()], [_dash("{}", "X", 0.7)], [_cube("{}", "X", 0.4)])

    assert check.comparison == "mastery" and check.fingerprint == "fp"
    assert check.formula == [("{}", "abbreviation=X")]
    assert check.coverage == [] and check.not_compared == {}
    [line] = check.lines
    assert "{}" in line and "abbreviation=X" in line
    assert "0.7" in line and "0.4" in line
    assert formula.Check.from_json(json.loads(json.dumps(check.to_json()))) == check


def test_verdicts_leave_an_agreeing_cell_to_coverage():
    check = _verdicts([_cell()], [_dash("{}", "X", 0.551)], [_cube("{}", "X", 0.549)])

    assert check.coverage == [("{}", "abbreviation=X")]
    assert check.formula == [] and check.not_compared == {} and check.lines == []


def test_verdicts_match_cells_by_cut_and_dims():
    cells = [_cell(), _cell(MIAMI)]
    dash = [_dash("{}", "X", 0.7), _dash(MIAMI, "X", 0.3)]
    cube = [_cube("{}", "X", 0.4), _cube(MIAMI, "X", 0.3)]

    check = _verdicts(cells, dash, cube)

    assert check.formula == [("{}", "abbreviation=X")]
    assert check.coverage == [(MIAMI, "abbreviation=X")]


def test_verdicts_say_the_rewrite_differs_when_a_self_check_misses():
    check = _verdicts(
        [_cell()],
        [_dash("{}", "X", 0.7)],
        [_cube("{}", "X", 0.4)],
        dash_self=[_dash("{}", "X", 0.5)],
    )

    assert check.not_compared == {formula.REWRITE_DIFFERS: [("{}", "abbreviation=X")]}
    assert check.formula == [] and check.coverage == []


def test_verdicts_say_no_rows_when_both_sides_are_empty():
    check = _verdicts([_cell()], [], [])

    assert check.not_compared == {formula.NO_ROWS: [("{}", "abbreviation=X")]}
    assert check.formula == [] and check.coverage == []


def test_verdicts_say_the_rewrite_differs_when_cube_s_self_check_misses():
    check = _verdicts(
        [_cell()],
        [_dash("{}", "X", 0.7)],
        [_cube("{}", "X", 0.4)],
        cube_self=[_cube("{}", "X", 0.45)],
    )

    assert check.not_compared == {formula.REWRITE_DIFFERS: [("{}", "abbreviation=X")]}


def test_verdicts_put_a_self_check_miss_before_no_rows():
    check = _verdicts([_cell()], [], [], cube_self=[_cube("{}", "X", 0.45)])

    assert check.not_compared == {formula.REWRITE_DIFFERS: [("{}", "abbreviation=X")]}


def test_verdicts_file_a_value_on_one_side_only_as_formula():
    check = _verdicts([_cell()], [], [_cube("{}", "X", 0.4)])

    assert check.formula == [("{}", "abbreviation=X")]
    assert check.coverage == [] and check.not_compared == {}


def test_verdicts_key_a_raw_dim_as_the_cell_keys_it():
    # The rows hold the day raw; the cell holds it as `value_key` text.
    day = date(2026, 10, 1)
    ref = ("{}", f"abbreviation={day}")
    cell = {
        **_cell(),
        "key": ref[1],
        "dims": [["abbreviation", pipeline.value_key(day)]],
    }

    check = formula.verdicts(
        DECIMALS,
        "fp",
        [cell],
        [{"__cut": "{}", "school": day, "value": 0.7}],
        [{"__cut": "{}", "abbreviation": datetime(2026, 10, 1), "value": 0.4}],
        [{"__cut": "{}", "school": day, "value": 0.6}],
        [{"__cut": "{}", "abbreviation": datetime(2026, 10, 1), "value": 0.5}],
    )

    assert check.formula == [ref]


def test_verdicts_say_the_rewrite_differs_on_a_repeated_cell():
    # 2 rows for one cell: neither is the cell's value.
    check = _verdicts(
        [_cell()], [_dash("{}", "X", 0.7), _dash("{}", "X", 0.4)],
        [_cube("{}", "X", 0.4)],
    )  # fmt: skip

    assert check.not_compared == {formula.REWRITE_DIFFERS: [("{}", "abbreviation=X")]}
    assert check.formula == [] and check.coverage == []


# --- filing checked cells -------------------------------------------------------

FILED = replace(COMPARISON, confirmed=True)
FILED_CFG = replace(CFG, comparisons=[FILED])


def _checked(fingerprint="fp1"):
    """A formula check of the result `_keep_result` keeps, filing its cell."""
    return formula.Check(
        "mastery",
        fingerprint,
        formula=[("{}", "abbreviation=X")],
        lines=["{} abbreviation=X: dashboard 0.7, Cube 0.4 on matched rows"],
    ).to_json()


class _MeasureCube:
    """Compiles the measure `compose_run` names in its candidate causes."""

    def compiled(self, query):
        return SimpleNamespace(sql="SELECT AVG(score_c) `v__pct` FROM `m`.`cube_t`")


def _keep_result(cache, check=None, *, moment=BUILD):
    """One latest result: a differing cell holding an unmatched group."""
    cell = pipeline.Cell(
        "mastery", "{}", "abbreviation=X", 0.6, 0.5, "differs", (("abbreviation", "X"),)
    )
    group = Group(
        "mastery", (("abbreviation", "X"),), "cube_only", 2, 1, cut_rows=(("{}", 2, 0),)
    )
    sides = pipeline.Sides(
        cells=[cell],
        groups=[group],
        fingerprints={"mastery": {"cube": "c", "dashboard": "d"}},
    )
    data = sides.to_json()
    if check is not None:
        data["formula_check"] = check
    held = latest.folder(cache / "v", CFG.fact)
    latest.write(
        held,
        "mastery",
        latest.Latest(
            moment=moment,
            fingerprint="fp1",
            entry=latest.entry_fingerprint(FILED),
            ran_at="",
            data=data,
            fact=CFG.fact,
        ),
    )
    return held


def _compose(cache, held):
    run = results.compose_run(
        FILED_CFG,
        [FILED],
        held,
        cube=_MeasureCube(),
        cube_host="h",
        totals=[],
        cache_root=cache,
        build=BUILD,
        folder=report.run_dir(cache, "v", BUILD),
        cost=0.0,
        echo=False,
    )
    return run, report.run_dir(cache, "v", BUILD) / "run.json"


def test_compose_files_checked_cells_as_formula(tmp_path):
    cache = tmp_path / "cache"
    run, run_json = _compose(cache, _keep_result(cache, _checked()))

    [diff] = run.applied.open_cells
    assert diff.kind == "formula" and diff.matched_only == 1
    assert diff.counts == {"differs": 1}
    assert diff.causes[0] == "1 differing cells differ on matched rows only"
    saved = json.loads(run_json.read_text())
    assert saved["applied"]["open_cells"][0]["matched_only"] == 1
    assert [c["kind"] for c in saved["diff_cells"]] == ["formula"]


def test_compose_ignores_a_check_of_another_result(tmp_path):
    other = _checked("fp0")
    run, run_json = _compose(tmp_path / "b", _keep_result(tmp_path / "b", other))
    _, plain_json = _compose(tmp_path / "a", _keep_result(tmp_path / "a"))

    [diff] = run.applied.open_cells
    assert diff.kind == "cells" and diff.matched_only == 0
    # A run with no check that counts saves exactly as before the check.
    assert run_json.read_text() == plain_json.read_text()
    assert "matched_only" not in plain_json.read_text()


@pytest.mark.parametrize(
    "check",
    [
        {"fingerprint": "fp1"},
        {"fingerprint": "fp1", "formula": [["{}"]]},
        {"fingerprint": "fp1", "formula": 3},
        ["fp1"],
    ],
)
def test_compose_ignores_a_malformed_check(tmp_path, check):
    cache = tmp_path / "cache"

    run, _ = _compose(cache, _keep_result(cache, check))

    [diff] = run.applied.open_cells
    assert diff.kind == "cells" and diff.matched_only == 0


def test_recompose_refuses_when_the_latest_results_moved_on(tmp_path):
    cache = tmp_path / "cache"
    held = _keep_result(cache)
    run, run_json = _compose(cache, held)
    latest.add_formula_check(held, "mastery", _checked())

    again = results.recompose(FILED_CFG, cache, run, run_json, cube=_MeasureCube())

    [diff] = again.applied.open_cells
    assert diff.kind == "formula" and diff.matched_only == 1
    saved = json.loads(run_json.read_text())
    assert saved["applied"]["open_cells"][0]["kind"] == "formula"

    later = Build(BUILD.start.replace(day=29), BUILD.end.replace(day=29), "j2")
    _keep_result(cache, moment=later)
    with pytest.raises(
        pipeline.Refusal, match="the run is not composed from the latest results"
    ):
        results.recompose(FILED_CFG, cache, run, run_json, cube=_MeasureCube())


# --- planning and running the check in `sort` ---------------------------------

PLANNED = replace(SIDE, confirmed=True, decimals=2)
PLAN_CFG = replace(CFG, fact="m.cube_t", comparisons=[PLANNED])
FPS = {"mastery": {"cube": "c", "dashboard": "d"}}
# The dashboard alone holds 3 and Cube alone holds 4, which moves Cube's cell
# to 0.8; on matched rows 1 and 2, both sides read 0.75.
PLAN_DASH = [(1, "a", 0.5, "X", "N", True, D1), (2, "a", 1.0, "X", "N", True, D1),
             (3, "a", 0.0, "X", "N", True, D1)]  # fmt: skip
PLAN_CUBE = [(1, "a", 0.5, "X", "N"), (2, "a", 1.0, "X", "N"), (4, "a", 0.9, "X", "N")]
REF = ("{}", "abbreviation=X")


class _RowsEx(_Ex):
    """`_Ex` that also compiles the comparison's ungrouped rows, `lea` as
    `lea` reads."""

    lea = "`c`.lea"

    def cube_sql(self, query, rows=False):
        if not rows:
            return super().cube_sql(query)
        columns = [m.split(".", 1)[1] for m in query["dimensions"]]
        select = ", ".join(
            f"{self.lea if c == 'lea' else f'`c`.{c}'} `v__{c}`" for c in columns
        )
        return f"SELECT {select} FROM m.cube_t AS `c`"


class _PlanWh(Wh):
    """`Wh` that knows the toy fact's columns."""

    def columns(self, dataset, name):
        return {"lea", "aid", "score_c", "abbreviation", "region_c"}


@pytest.fixture
def offline(monkeypatch):
    """Cube and the run's row SQL, compiled over the toy tables."""
    ex = _RowsEx()
    monkeypatch.setattr(pipeline, "Expand", lambda *a, **k: ex)
    monkeypatch.setattr(
        pipeline, "row_sides", lambda cfg, comparison, **k: _side_sides(cfg, comparison)
    )
    return ex


def _plan_run():
    """A run whose one differing cell holds a dashboard-only group."""
    group = Group(
        "mastery", (("abbreviation", "X"),), "dashboard_only", 1, 1,
        cut_rows=(("{}", 0, 1),),
    )  # fmt: skip
    return RunResult(
        view="v",
        moment=BUILD,
        measures=[],
        applied=Applied(open=[group]),
        diff_cells=[_cell(dashboard=0.5, cube=0.8)],
        fingerprints=FPS,
    )


def _plan(duck, run, *, labelled=True):
    """`plan` over the toy tables, the run's rows saved as `compare` saves them."""
    _side_tables(duck, PLAN_DASH, PLAN_CUBE)
    wh = _PlanWh(duck)
    table = table_id("v", BUILD, "mastery")
    duck.rows("DROP TABLE IF EXISTS __joined")
    sides = _side_sides(PLAN_CFG, PLANNED)
    for statement in compare.save_script(
        PLAN_CFG, PLANNED, sides, table_sql(table), None
    ):
        duck.rows(statement)
    if labelled:
        wh.labels[table] = labels(
            "v",
            BUILD,
            "mastery",
            pipeline.checkpoint_fingerprint(PLANNED, FPS["mastery"]),
        )
    got = formula.plan(
        PLAN_CFG,
        run,
        PLANNED,
        fingerprint="fp",
        wh=wh,
        cube=None,
        prepared=Prepared(schools=set()),
    )
    return got, wh


def test_plan_builds_four_priced_queries(duck, offline):
    run = _plan_run()

    job, wh = _plan(duck, run)

    assert isinstance(job, formula.Job)
    assert (job.comparison, job.fingerprint) == ("mastery", "fp")
    assert job.cells == run.diff_cells
    assert set(job.sql) == {"dashboard", "cube", "dashboard_self", "cube_self"}
    assert all("__matched" in job.sql[k] for k in ("dashboard", "cube"))
    assert all("__matched" not in job.sql[k] for k in ("dashboard_self", "cube_self"))
    check = formula.run_job(job, PLANNED, wh)
    assert [sql for sql, _ in wh.ran] == list(job.sql.values())
    assert all(timeout == TIMEOUT_S for _, timeout in wh.ran)
    # Both sides read 0.75 on matched rows: the rows explain the cell.
    assert check.coverage == [REF] and check.not_compared == {}


def test_plan_has_nothing_to_check_without_a_cell_holding_a_group(duck, offline):
    run = replace(_plan_run(), applied=Applied())

    assert _plan(duck, run)[0] is None


def test_plan_says_compare_again_when_the_saved_rows_are_gone(duck, offline):
    check, _ = _plan(duck, _plan_run(), labelled=False)

    assert isinstance(check, formula.Check)
    assert check.not_compared == {formula.SAVED_GONE: [REF]}
    assert check.formula == [] and check.coverage == []


def test_plan_falls_back_when_the_grain_is_an_expression(duck, offline):
    offline.lea = "CAST(`c`.lea AS INT64)"

    check, _ = _plan(duck, _plan_run())

    assert check.not_compared == {
        "grain column lea is an expression, not a fact column": [REF]
    }


def test_plan_falls_back_when_the_grain_sits_on_a_joined_table(
    duck, offline, monkeypatch
):
    # The joined table's `lea` may mean something else than the fact's own
    # `lea`, so filtering the fact by it would be a guess.
    compiled = offline.cube_sql

    def joined(query, rows=False):
        if not rows:
            return compiled(query)
        return (
            "SELECT `s`.lea `v__lea`, `s`.aid `v__aid` FROM m.cube_t AS `c` "
            "LEFT JOIN m.dim_students AS `s` ON `s`.k = `c`.k"
        )

    monkeypatch.setattr(offline, "cube_sql", joined)

    check, _ = _plan(duck, _plan_run())

    assert check.not_compared == {
        "the grain columns sit on m.dim_students, which Cube's filtered tables "
        "do not include": [REF]
    }


def test_plan_says_cube_refused_when_cube_refuses_its_sql(duck, offline, monkeypatch):
    def refused(query, rows=False):
        raise CubeRefusal("the compiled query reads another fact")

    monkeypatch.setattr(offline, "cube_sql", refused)

    check, _ = _plan(duck, _plan_run())

    assert check.not_compared == {formula.CUBE_REFUSED: [REF]}


def _job():
    return formula.Job(
        "mastery",
        "fp",
        [_cell()],
        {"dashboard": "q1", "cube": "q2", "dashboard_self": "q3", "cube_self": "q4"},
    )


def test_run_job_falls_back_on_a_bigquery_error_with_its_job_only():
    class Refusing:
        def rows(self, sql, timeout_s=None):
            exc = BadRequest(
                "No matching signature for value 'Student 12345'",
                errors=[{"reason": "invalidQuery"}],
            )
            setattr(exc, JOB_ID, "job-9")
            raise exc

    class Capped:
        def rows(self, sql, timeout_s=None):
            raise CostCapError("spent $5.00, over the $5.00 cap")

    check = formula.run_job(_job(), DECIMALS, Refusing())

    why = "BigQuery refused it (job job-9, invalidQuery); sort again"
    assert check.not_compared == {why: [REF]}
    assert "12345" not in json.dumps(check.to_json())
    assert formula.run_job(_job(), DECIMALS, Capped()).not_compared == {
        "a cap stopped it; sort again with a higher --max-usd": [REF]
    }


def test_run_job_falls_back_when_its_warehouse_fails_outside_bigquery(capsys):
    class Expired:
        def rows(self, sql, timeout_s=None):
            raise RefreshError("Reauthentication is needed.")

    check = formula.run_job(_job(), DECIMALS, Expired())

    assert check.not_compared == {formula.RUN_FAILED: [REF]}
    assert "Reauthentication is needed." in capsys.readouterr().out


def test_label_discloses_unchecked_cells_masked():
    items = [
        {"id": "mastery:cells", "evidence": ["covered"],
         "evidence_posted": ["covered, posted"]},
        {"id": "mastery:formula", "evidence": ["f"], "evidence_posted": ["f"]},
    ]  # fmt: skip
    gone = [("{}", f"abbreviation=S{i}") for i in range(3)]
    empty = [("{}", f"abbreviation=T{i}") for i in range(12)]
    checks = {
        "mastery": formula.Check(
            "mastery",
            "fp",
            coverage=[REF],
            not_compared={formula.SAVED_GONE: gone, formula.NO_ROWS: empty},
        ),
        "other": formula.Check("other", "fp", coverage=[REF]),
    }

    counts = formula.label(items, checks)

    assert counts == {"mastery": {formula.SAVED_GONE: 3, formula.NO_ROWS: 12}}
    cells, other = items
    shut = "cells closed by coverage only"
    assert cells["evidence"] == [
        f"formulas not compared: {formula.SAVED_GONE} (3 {shut})",
        f"formulas not compared: {formula.NO_ROWS} (12 {shut})",
        "covered",
    ]
    assert cells["evidence_posted"] == [
        f"formulas not compared: {formula.SAVED_GONE} (<10 {shut})",
        f"formulas not compared: {formula.NO_ROWS} (12 {shut})",
        "covered, posted",
    ]
    assert other["evidence"] == ["f"]
    assert "S1" not in json.dumps(items) and "T1" not in json.dumps(items)
