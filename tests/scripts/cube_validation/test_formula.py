import json
import re
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import compare, formula, latest, pipeline, report, results

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
from cube_validation.reconcile import Group, joined_ctes

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.saved import labels, table_id, table_sql

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo, as_of, repin, utc_literal

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.trace import TIMEOUT_S, Prepared
from google.api_core.exceptions import BadRequest
from google.auth.exceptions import RefreshError

from .test_explain import SIDES, Wh

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
    (other,) = duck.rows(
        f"{sql}\nSELECT __key FROM __joined_keys WHERE NOT __all_match"
    )
    saved = duck.rows(
        f"SELECT {formula.key_sql(['__gd0', '__gd1'], [False, False])} AS k "
        "FROM saved_t"
    )
    assert other["__key"] is not None
    assert [r["k"] for r in saved] == [other["__key"]]


def _two_read_matched_sql(cfg, comparison, sides, saved_table) -> str:
    """The matched keys as 2 reads of `joined` build them: the keys with a
    `match` row, less the keys with any other row and the saved keys."""
    n = len(comparison.rows.grain)
    args, kwargs = pipeline.reconcile_args(cfg, comparison, sides)
    ctes, _ = joined_ctes(*args, keys=True, moved=True, **kwargs)
    joined_key = formula._keyed([f"__k{i}" for i in range(n)])
    plain = [False] * n
    dash_key = formula.key_sql([f"__gd{i}" for i in range(n)], plain)
    cube_key = formula.key_sql([f"__gc{i}" for i in range(n)], plain)
    matched = "bucket = 'match' AND __cin IS NOT NULL AND __din IS NOT NULL"
    return (
        f"{ctes},\n"
        f"__match AS (SELECT {joined_key} AS __key FROM joined WHERE {matched}),\n"
        f"__other AS (SELECT {joined_key} AS __key FROM joined "
        f"WHERE NOT ({matched})),\n"
        f"__saved AS (SELECT {dash_key} AS __key FROM {saved_table} "
        "WHERE bucket != 'cube_only' UNION DISTINCT "
        f"SELECT {cube_key} AS __key FROM {saved_table} "
        "WHERE bucket != 'dashboard_only'),\n"
        "__matched AS (SELECT __key FROM __match WHERE __key IS NOT NULL "
        "EXCEPT DISTINCT SELECT __key FROM __other "
        "EXCEPT DISTINCT SELECT __key FROM __saved)\n"
        "SELECT __key FROM __matched"
    )


def test_matched_keys_of_one_read_equal_those_of_two_reads(duck):
    # 1 matches; 2 matches with NULL scores on both sides; 3 is NULL on the
    # dashboard only; 4 holds a matching and a differing copy; Cube alone
    # holds 5 and the dashboard alone 6; 7 matches twice; a NULL student
    # matches. Saved, then 8 joins both sides, so only the saved rows drop it.
    cube = [(1, "a", 10, "X"), (2, "a", None, "X"), (3, "a", 10, "X"),
            (4, "a", 10, "X"), (4, "a", 10, "X"), (5, "a", 10, "X"),
            (7, "a", 10, "X"), (7, "a", 10, "X"), (None, "a", 10, "X"),
            (8, "a", 10, "X")]  # fmt: skip
    dash = [(1, "a", 10, "X"), (2, "a", None, "X"), (3, "a", None, "X"),
            (4, "a", 10, "X"), (4, "a", 99, "X"), (6, "a", 10, "X"),
            (7, "a", 10, "X"), (7, "a", 10, "X"), (None, "a", 10, "X")]  # fmt: skip
    _tables(duck, cube, dash)
    _save(duck)
    _tables(duck, cube, [*dash, (8, "a", 10, "X")])

    old = duck.rows(_two_read_matched_sql(CFG, COMPARISON, VALUED, SAVED))
    new = duck.rows(
        formula.matched_ctes(CFG, COMPARISON, VALUED, SAVED)
        + "\nSELECT __key FROM __matched"
    )

    def students(rows):
        return sorted(int(float(json.loads(r["__key"])["k0"])) for r in rows)

    assert students(new) == students(old) == [1, 2, 7]


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
        return TableInfo("TABLE")


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

FACT_X = ["kipptaf_marts.fct_x"]


def test_fact_grain_maps_each_member_to_its_fact_column():
    sql = (
        "SELECT `f`.student_number `v__student`, `f`.item_id `v__item` "
        "FROM kipptaf_marts.fct_x AS `f`"
    )

    grain = formula.fact_grain(sql, "v", ["student", "item"], FACT_X)

    assert (grain.table, grain.alias, grain.hops) == ("kipptaf_marts.fct_x", "f", ())
    assert grain.columns == ["student_number", "item_id"]


def test_fact_grain_reads_a_grain_on_an_also_facts_table_as_today():
    sql = (
        "SELECT `g`.student_number `v__student` FROM kipptaf_marts.fct_x AS `f` "
        "LEFT JOIN kipptaf_marts.fct_goals AS `g` ON `g`.k = `f`.k"
    )

    grain = formula.fact_grain(
        sql, "v", ["student"], [*FACT_X, "KIPPTAF_MARTS.fct_goals"]
    )

    assert (grain.table, grain.alias, grain.hops) == (
        "kipptaf_marts.fct_goals", "g", (),
    )  # fmt: skip


def test_fact_grain_refuses_an_expression():
    sql = (
        "SELECT CAST(`f`.a AS STRING) `v__student`, `f`.item_id `v__item` "
        "FROM kipptaf_marts.fct_x AS `f`"
    )

    with pytest.raises(
        formula.NotCompared, match="grain column student is an expression"
    ):
        formula.fact_grain(sql, "v", ["student", "item"], FACT_X)


def test_fact_grain_refuses_a_subquery_alias():
    sql = (
        "SELECT `s`.student_number `v__student`, `s`.item_id `v__item` "
        "FROM (SELECT * FROM kipptaf_marts.fct_x) AS `s`"
    )

    with pytest.raises(
        formula.NotCompared, match="grain column student is read from a subquery"
    ):
        formula.fact_grain(sql, "v", ["student", "item"], FACT_X)


def test_fact_grain_refuses_a_member_missing_from_the_select():
    sql = "SELECT `f`.item_id `v__item` FROM kipptaf_marts.fct_x AS `f`"

    with pytest.raises(
        formula.NotCompared, match="grain member student is not in Cube's row SQL"
    ):
        formula.fact_grain(sql, "v", ["student", "item"], FACT_X)


def test_fact_grain_refuses_sql_that_is_no_single_select():
    sql = "SELECT 1 `v__student` UNION ALL SELECT 2 `v__student`"

    with pytest.raises(formula.NotCompared, match="is not a single SELECT"):
        formula.fact_grain(sql, "v", ["student"], FACT_X)


def test_fact_grain_refuses_a_table_with_no_dataset():
    sql = "SELECT `f`.student_number `v__student` FROM fct_x AS `f`"

    with pytest.raises(
        formula.NotCompared,
        match="grain column student sits on a CTE or a table with no dataset",
    ):
        formula.fact_grain(sql, "v", ["student"], FACT_X)


def test_fact_grain_refuses_a_column_of_no_table_it_reads():
    sql = "SELECT student_number `v__student` FROM kipptaf_marts.fct_x AS `f`"

    with pytest.raises(
        formula.NotCompared,
        match="grain column student names no table of the outer FROM",
    ):
        formula.fact_grain(sql, "v", ["student"], FACT_X)


# Cube's row SQL as it compiles a DDI query: the student 3 joins from the
# fact, the assessment 1, the response type on the fact, and a dates dim the
# grain does not need.
JOINED_ROWS = (
    "SELECT `students`.lea `v__student`, `admins`.aid `v__item`, "
    "`scores`.rtype `v__rtype`, `dates`.day `v__day` "
    "FROM  kipptaf_marts.fct_s  AS `scores`\n"
    "LEFT JOIN  kipptaf_marts.dim_sections  AS `sections` "
    "ON `sections`.section_key = `scores`.section_key\n"
    "LEFT JOIN  kipptaf_marts.dim_enrollments  AS `enrollments` "
    "ON `enrollments`.enrollment_key = `sections`.enrollment_key\n"
    "LEFT JOIN  kipptaf_marts.dim_students  AS `students` "
    "ON `students`.student_key = `enrollments`.student_key\n"
    "LEFT JOIN  kipptaf_marts.dim_admins  AS `admins` "
    "ON `admins`.admin_key = `scores`.admin_key AND `admins`.year = `scores`.year\n"
    "LEFT JOIN  kipptaf_marts.dim_dates  AS `dates` "
    "ON `dates`.date_key = `scores`.date_key"
)
JOINED_FACTS = ["kipptaf_marts.fct_s"]


def test_fact_grain_follows_cube_s_joins_from_the_fact():
    grain = formula.fact_grain(
        JOINED_ROWS, "v", ["student", "item", "rtype"], JOINED_FACTS
    )

    assert (grain.table, grain.alias) == ("kipptaf_marts.fct_s", "scores")
    assert grain.keys == (
        ("students", "lea"), ("admins", "aid"), ("scores", "rtype"),
    )  # fmt: skip
    # Each join on a grain member's path, in Cube's order; `dates` is on none.
    assert grain.hops == (
        formula.Hop("sections", "kipptaf_marts.dim_sections", "LEFT JOIN",
                    "`sections`.`section_key` = `scores`.`section_key`"),
        formula.Hop("enrollments", "kipptaf_marts.dim_enrollments", "LEFT JOIN",
                    "`enrollments`.`enrollment_key` = `sections`.`enrollment_key`"),
        formula.Hop("students", "kipptaf_marts.dim_students", "LEFT JOIN",
                    "`students`.`student_key` = `enrollments`.`student_key`"),
        formula.Hop("admins", "kipptaf_marts.dim_admins", "LEFT JOIN",
                    "`admins`.`admin_key` = `scores`.`admin_key` "
                    "AND `admins`.`year` = `scores`.`year`"),
    )  # fmt: skip


def test_fact_grain_follows_the_joins_to_a_grain_on_one_dim():
    grain = formula.fact_grain(JOINED_ROWS, "v", ["student"], JOINED_FACTS)

    assert grain.keys == (("students", "lea"),)
    assert [h.alias for h in grain.hops] == ["sections", "enrollments", "students"]


def test_fact_grain_keeps_an_inner_join_on_the_path():
    sql = JOINED_ROWS.replace(
        "LEFT JOIN  kipptaf_marts.dim_admins", "INNER JOIN kipptaf_marts.dim_admins"
    )

    grain = formula.fact_grain(sql, "v", ["item"], JOINED_FACTS)

    assert [(h.alias, h.kind) for h in grain.hops] == [("admins", "INNER JOIN")]


@pytest.mark.parametrize(
    ("on", "why"),
    [
        ("`admins`.admin_key = `scores`.admin_key OR `admins`.k = `scores`.k",
         "is not on an equality of columns"),
        ("`admins`.admin_key >= `scores`.admin_key",
         "is not on an equality of columns"),
        ("CAST(`admins`.admin_key AS STRING) = `scores`.admin_key",
         "is not on an equality of columns"),
        ("`admins`.admin_key = 1", "is not on an equality of columns"),
        ("TRUE", "is not on an equality of columns"),
        ("`admins`.admin_key = `scores`.admin_key AND `admins`.k = `dates`.k",
         "does not compare it with exactly one table before it"),
        ("`admins`.admin_key = `admins`.other_key",
         "does not compare it with exactly one table before it"),
    ],
)  # fmt: skip
def test_fact_grain_refuses_a_path_join_on_anything_but_column_equalities(on, why):
    sql = JOINED_ROWS.replace(
        "ON `admins`.admin_key = `scores`.admin_key AND `admins`.year = `scores`.year",
        f"ON {on}",
    )

    with pytest.raises(
        formula.NotCompared, match=f"the join to admins on the grain's path {why}"
    ):
        formula.fact_grain(sql, "v", ["item"], JOINED_FACTS)


@pytest.mark.parametrize("join", ["RIGHT JOIN", "FULL JOIN", "CROSS JOIN", "USING"])
def test_fact_grain_refuses_a_path_join_of_another_kind(join):
    on = "ON `admins`.admin_key = `scores`.admin_key AND `admins`.year = `scores`.year"
    sql = {
        "CROSS JOIN": JOINED_ROWS.replace(
            f"LEFT JOIN  kipptaf_marts.dim_admins  AS `admins` {on}",
            "CROSS JOIN kipptaf_marts.dim_admins AS `admins`",
        ),
        "USING": JOINED_ROWS.replace(on, "USING (admin_key)"),
    }.get(
        join,
        JOINED_ROWS.replace("LEFT JOIN  kipptaf_marts.dim_admins", f"{join} "
                            "kipptaf_marts.dim_admins"),
    )  # fmt: skip
    why = {"USING": "is not on an equality of columns"}.get(
        join, "is not a LEFT or INNER join"
    )

    with pytest.raises(
        formula.NotCompared, match=f"the join to admins on the grain's path {why}"
    ):
        formula.fact_grain(sql, "v", ["item"], JOINED_FACTS)


def test_fact_grain_refuses_a_grain_no_join_from_the_fact_reaches():
    # The goals table is read first and the fact joined to it, so no chain of
    # joins leads from the fact to the goals.
    sql = (
        "SELECT `goals`.school `v__student`, `f`.item_id `v__item` "
        "FROM kipptaf_marts.fct_goals AS `goals` "
        "LEFT JOIN kipptaf_marts.fct_x AS `f` ON `f`.school = `goals`.school"
    )

    with pytest.raises(
        formula.NotCompared,
        match="grain member student sits on goals, which no chain of joins from "
        "the fact reaches",
    ):
        formula.fact_grain(
            sql, "v", ["student", "item"],
            ["kipptaf_marts.fct_x", "kipptaf_marts.fct_goals"],
        )  # fmt: skip


def test_fact_grain_refuses_a_path_when_the_fact_is_not_read():
    with pytest.raises(
        formula.NotCompared,
        match="the grain sits off the fact, and Cube's row SQL does not read the "
        "fact kipptaf_marts.fct_other",
    ):
        formula.fact_grain(JOINED_ROWS, "v", ["student"], ["kipptaf_marts.fct_other"])


def test_fact_grain_refuses_a_path_when_the_fact_is_read_twice():
    # Which read of the fact the path starts at would be a guess.
    sql = JOINED_ROWS.replace(
        "kipptaf_marts.dim_sections  AS `sections`",
        "kipptaf_marts.fct_s  AS `sections`",
    )

    with pytest.raises(
        formula.NotCompared,
        match="the grain sits off the fact, and Cube's row SQL does not read the "
        "fact kipptaf_marts.fct_s once",
    ):
        formula.fact_grain(sql, "v", ["student"], JOINED_FACTS)


def test_fact_grain_refuses_a_path_through_an_also_facts_table():
    # Another fact on the path is read as is, so its own rows would move the
    # key the fact is filtered by.
    with pytest.raises(
        formula.NotCompared,
        match="the join to enrollments on the grain's path reads "
        "kipptaf_marts.dim_enrollments, one of the view's also_facts",
    ):
        formula.fact_grain(
            JOINED_ROWS, "v", ["student"],
            [*JOINED_FACTS, "KIPPTAF_MARTS.dim_enrollments"],
        )  # fmt: skip


def test_fact_grain_refuses_a_path_through_a_subquery():
    sql = JOINED_ROWS.replace(
        "kipptaf_marts.dim_sections  AS `sections`",
        "(SELECT * FROM kipptaf_marts.dim_sections)  AS `sections`",
    )

    with pytest.raises(
        formula.NotCompared,
        match="the join to sections on the grain's path reads a subquery or a "
        "table with no dataset",
    ):
        formula.fact_grain(sql, "v", ["student"], JOINED_FACTS)


def test_fact_grain_refuses_sql_it_cannot_parse():
    with pytest.raises(formula.NotCompared, match="Cube's SQL could not be parsed"):
        formula.fact_grain("SELECT `f.a FROM (", "v", ["student"], FACT_X)


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


def test_rewrite_keeps_cube_s_spelling_of_the_table():
    # BigQuery dataset and table names are case-sensitive.
    upper = PINNED.replace("`teamster-332318.m.fct`", "`teamster-332318.M.Fct`")

    sql = formula.rewrite_cube_sql(upper, ["m.fct"], ["lea"], [False], keep=False)

    assert "`teamster-332318.m.fct`" not in sql
    assert sql.count("(SELECT * FROM `teamster-332318.M.Fct` FOR SYSTEM_TIME") == 2


def test_rewrite_quotes_a_grain_column_named_by_a_reserved_word(duck):
    duck.table("fct", '"order" BIGINT, v BIGINT', [(1, 10), (2, 20)])
    pinned = (
        "SELECT SUM(`f`.v) AS v FROM `teamster-332318.m.fct` AS `f` "
        f"FOR SYSTEM_TIME AS OF TIMESTAMP '{END}'"
    )
    matched = (
        f"WITH __matched AS (SELECT {formula.key_sql(['o'], [False])} AS __key "
        "FROM (SELECT 1 AS o))\n"
    )

    sql = formula.rewrite_cube_sql(pinned, ["m.fct"], ["order"], [False], keep=True)

    # sqlglot reads a bare `order` where BigQuery refuses it, so the text
    # carries the check and DuckDB only that the quoted key still matches.
    assert "CAST(`order` AS STRING)" in sql and "CAST(order " not in sql
    assert [int(r["v"]) for r in duck.rows(matched + sql)] == [10]


@pytest.mark.parametrize("alias", [" AS `p`", ""])
def test_rewrite_refuses_a_read_through_a_pivot_by_name(alias):
    # `as_of` wraps a table read through a PIVOT, so the read has no alias.
    sql = (
        "SELECT * FROM (SELECT * FROM `teamster-332318.m.fct` "
        f"FOR SYSTEM_TIME AS OF TIMESTAMP '{END}'){alias}\n"
        "PIVOT(SUM(v) FOR k IN ('a'))"
    )

    with pytest.raises(
        formula.NotCompared, match="Cube's SQL reads m.fct through a PIVOT"
    ):
        formula.rewrite_cube_sql(sql, ["m.fct"], ["lea"], [False], keep=True)


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
        grain=formula.Grain(
            "m.cube_t", "c", tuple(("c", p.cube) for p in comparison.rows.grain)
        ),
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


# --- the Cube side through Cube's joins ---------------------------------------

# A toy DDI: the student 3 joins from the scores fact (the middle one a view,
# as on DDI), the item and its day 1 join away, the response type on the
# fact, and a dates dim on no member's path.
_JOINS = (
    "LEFT JOIN  m.dim_sections  AS `sections` "
    "ON `sections`.section_key = `scores`.section_key\n"
    "LEFT JOIN  m.dim_enrollments  AS `enrollments` "
    "ON `enrollments`.enrollment_key = `sections`.enrollment_key\n"
    "LEFT JOIN  m.dim_students  AS `students` "
    "ON `students`.student_key = `enrollments`.student_key\n"
    "LEFT JOIN  m.dim_admins  AS `admins` "
    "ON `admins`.admin_key = `scores`.admin_key\n"
    "LEFT JOIN  m.dim_dates  AS `dates` ON `dates`.date_key = `scores`.date_key"
)
# Cube's expression for each member.
_MEMBER = {
    "lea": "`students`.lea", "aid": "`admins`.aid", "day": "`admins`.day",
    "rtype": "`scores`.rtype", "score_c": "`scores`.score",
    "abbreviation": "`scores`.school",
}  # fmt: skip
JOINED = Comparison(
    id="mastery",
    measure="pct",
    dashboard_view="d.dash_j",
    sheet_query="AVG(score)",
    dims=[ColumnPair("school", "abbreviation")],
    rows=RowSpec(
        grain=[
            ColumnPair("student", "lea"),
            ColumnPair("item", "aid"),
            ColumnPair("rtype", "rtype"),
        ],
        values=[ColumnPair("score", "score_c")],
    ),  # fmt: skip
)
JOINED_CFG = ViewConfig(view="v", fact="m.fct_s", comparisons=[JOINED])
# Scores (section, admin, date, response type, score, school): 1 and 2
# match; Cube alone holds 4; 5 sits on another item on each side; the last
# score's section is unknown, so its student is NULL and it never matches.
SCORES = [(11, 41, 1, "r", 0.5, "X"), (12, 41, 1, "r", 1.0, "X"),
          (14, 41, 1, "r", 0.0, "X"), (15, 42, 1, "r", 0.2, "X"),
          (99, 41, 1, "r", 0.9, "X")]  # fmt: skip
STUDENTS = [(31, 1), (32, 2), (34, 4), (35, 5)]
DASH_J = [(1, "a", "r", 0.5, "X", T1), (2, "a", "r", 1.0, "X", T1),
          (3, "a", "r", 0.0, "X", T1), (5, "a", "r", 0.2, "X", T1)]  # fmt: skip


class _JoinCatalog:
    """`dim_enrollments` a view over `enroll_base`; every other relation a
    table."""

    def table(self, dataset, name):
        return TableInfo("VIEW" if name == "dim_enrollments" else "TABLE")

    def view_sql_as_of(self, dataset, name, ts):
        return "select * from `teamster-332318`.`m`.`enroll_base`"


class _JoinEx:
    """`pipeline.Expand` over the toy DDI: the rows through every join, the
    cells `measure` by the query's dims from `cells_from` (the fact and the
    dates dim unless set)."""

    measure = "AVG(`scores`.score)"
    cells_from = (
        "FROM  m.fct_s  AS `scores`\n"
        "LEFT JOIN  m.dim_dates  AS `dates` ON `dates`.date_key = `scores`.date_key"
    )

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def cube_sql(self, query, rows=False):
        members = [m.split(".", 1)[1] for m in query["dimensions"]]
        select = [f"{_MEMBER[m]} `v__{m}`" for m in members]
        if rows:
            return f"SELECT {', '.join(select)} FROM  m.fct_s  AS `scores`\n{_JOINS}"
        where = " AND ".join(
            f"{_MEMBER[f['member'].split('.', 1)[1]]} = {pipeline.lit(f['values'][0])}"
            for f in query["filters"]
        )
        group = ", ".join(str(i + 1) for i in range(len(members)))
        return (
            f"SELECT {', '.join([*select, f'{self.measure} `v__pct`'])} "
            f"{self.cells_from}\nWHERE {where or 'TRUE'} GROUP BY {group}"
        )

    def at(self, sql, ts):
        return as_of(sql, ts, _JoinCatalog())


def _joined_tables(duck, scores=SCORES, students=STUDENTS, dash=DASH_J):
    duck.table(
        "fct_s",
        "section_key BIGINT, admin_key BIGINT, date_key BIGINT, rtype VARCHAR, "
        "score DOUBLE, school VARCHAR",
        scores,
    )
    duck.table("dim_sections", "section_key BIGINT, enrollment_key BIGINT",
               [(11, 21), (12, 22), (14, 24), (15, 25)])  # fmt: skip
    duck.table("enroll_base", "enrollment_key BIGINT, student_key BIGINT",
               [(21, 31), (22, 32), (24, 34), (25, 35)])  # fmt: skip
    duck.table("dim_students", "student_key BIGINT, lea BIGINT", students)
    duck.table("dim_admins", "admin_key BIGINT, aid VARCHAR, day TIMESTAMP",
               [(41, "a", T1), (42, "b", T1)])  # fmt: skip
    duck.table("dim_dates", "date_key BIGINT", [(1,)])
    duck.table(
        "dash_j",
        "student BIGINT, item VARCHAR, rtype VARCHAR, score DOUBLE, school VARCHAR, "
        "day TIMESTAMP",
        dash,
    )


def _joined_sides(cfg, comparison, shared) -> pipeline.RowSides:
    """The row SQL `compare` reconciles over the toy DDI, pinned as
    `pipeline.row_sides` pins it; the dashboard's rows read `shared`."""
    ex = _JoinEx()
    cube = ex.at(ex.cube_sql(pipeline.row_query("v", comparison), rows=True), BUILD.end)
    return pipeline.RowSides(
        cube=cube,
        dashboard=AsOf(pipeline.dashboard_rows_sql(cfg, comparison), shared,
                       frozenset()),
        cube_rows_sql=repin(cube.sql, sorted(cube.tables & shared), BUILD.end,
                            BUILD.start),
        columns=pipeline.unique(p.cube for p in pipeline.row_pairs(comparison)),
    )  # fmt: skip


def _joined_cells(
    duck, comparison=JOINED, cfg=JOINED_CFG, *, keep=True, shared=frozenset(),
    ex=None,
):  # fmt: skip
    """The Cube side as `sort` runs it over the toy DDI, by (cut, school),
    and the whole query."""
    cfg = replace(cfg, comparisons=[comparison])
    sides = _joined_sides(cfg, comparison, shared)
    _save(duck, cfg, sides)
    ex = ex or _JoinEx()
    grain = formula.fact_grain(
        ex.cube_sql(pipeline.row_query("v", comparison), rows=True),
        "v",
        [p.cube for p in comparison.rows.grain],
        [cfg.fact],
    )
    body = formula.cube_side_sql(
        cfg, comparison, pipeline.comparison_cuts(comparison), BUILD,
        ex=ex, sides=sides, tables=[grain.table], grain=grain, keep=keep,
    )  # fmt: skip
    sql = body
    if keep:
        ctes = formula.matched_ctes(cfg, comparison, sides, SAVED)
        sql = f"{ctes}\nSELECT * FROM (\n{body}\n)"
    cells = {(r["__cut"], r["abbreviation"]): r["value"] for r in duck.rows(sql)}
    return cells, sql


def _joined_run(duck, comparison=JOINED, ex=None) -> dict:
    """The run's own Cube cells: Cube's cell SQL as compiled, by (cut, school)."""
    ex = ex or _JoinEx()
    return {
        (pipeline.cut_label(cut), r["abbreviation"]): r["value"]
        for cut in pipeline.comparison_cuts(comparison)
        for r in duck.rows(
            pipeline.wrap_cube(
                ex.at(
                    ex.cube_sql(pipeline.cell_query("v", comparison, cut)), BUILD.end
                ).sql,
                "v",
                ["abbreviation"],
                set(),
                "pct",
            )  # fmt: skip
        )
    }


def _moments(sql) -> dict[str, set[str]]:
    """Each table's moments in `sql`, by `dataset.table`."""
    found: dict[str, set[str]] = {}
    for table, at in re.findall(
        r"`teamster-332318\.(\w+\.\w+)`(?:\s+AS\s+`?\w+`?)?\s+"
        r"FOR SYSTEM_TIME AS OF TIMESTAMP '([^']+)'",
        sql,
        re.IGNORECASE,
    ):
        found.setdefault(table, set()).add(at)
    return found


def test_cube_side_follows_cube_s_joins_to_matched_rows(duck):
    _joined_tables(duck)
    cfg = replace(JOINED_CFG, comparisons=[JOINED])
    sides = _joined_sides(cfg, JOINED, frozenset())

    run = _joined_run(duck)
    kept, sql = _joined_cells(duck)
    whole, _ = _joined_cells(duck, keep=False)
    dash = duck.rows(
        formula.matched_ctes(cfg, JOINED, sides, SAVED) + "\nSELECT * FROM (\n"
        + formula.dashboard_side_sql(cfg, JOINED, [{}], BUILD, _Catalog(), keep=True)
        + "\n)"
    )  # fmt: skip

    # The run's cell holds every score, the unknown student's included.
    assert run == {("{}", "X"): pytest.approx(0.52)}
    assert whole == run
    # Matched rows are 1 and 2 only, keyed through 3 joins and 1.
    assert kept == {("{}", "X"): pytest.approx(0.75)}
    assert [r["value"] for r in dash] == [pytest.approx(0.75)]
    assert "LEFT JOIN `teamster-332318.m.dim_students` AS `students`" in sql
    # Cube's own cell SQL joins no grain table, so only the subquery does.
    assert sql.count("`teamster-332318.m.dim_students`") == 2
    # The view on the path is read through its own SQL, as the run read it.
    assert "dim_enrollments" not in sql and "enroll_base" in sql


def test_cube_side_through_joins_reads_each_table_at_one_moment(duck):
    _joined_tables(duck)
    shared = frozenset({"m.dim_students", "m.fct_s"})

    kept, sql = _joined_cells(duck, shared=shared)

    moments = _moments(sql)
    assert all(len(at) == 1 for at in moments.values()), moments
    assert moments["m.dim_students"] == {START}
    assert moments["m.fct_s"] == {START}
    assert moments["m.dim_sections"] == moments["m.enroll_base"] == {END}
    assert kept == {("{}", "X"): pytest.approx(0.75)}


def _joined_grain(comparison=JOINED, cfg=JOINED_CFG):
    return formula.fact_grain(
        _JoinEx().cube_sql(pipeline.row_query("v", comparison), rows=True),
        "v",
        [p.cube for p in comparison.rows.grain],
        [cfg.fact, *cfg.also_facts],
    )


def test_cube_side_through_joins_when_the_cells_join_the_same_tables(duck):
    # DDI's real shape: Cube's cell SQL itself joins the path's tables under
    # the aliases the subquery uses inside, each name in its own scope.
    _joined_tables(duck)
    ex = _JoinEx(cells_from=f"FROM  m.fct_s  AS `scores`\n{_JOINS}")
    shared = frozenset({"m.dim_students"})

    run = _joined_run(duck, ex=ex)
    whole, _ = _joined_cells(duck, keep=False, ex=ex, shared=shared)
    kept, sql = _joined_cells(duck, ex=ex, shared=shared)

    assert run == {("{}", "X"): pytest.approx(0.52)}
    assert whole == run
    assert kept == {("{}", "X"): pytest.approx(0.75)}
    # The students are read by the run's rows, the cells and the subquery,
    # every time at the moment the dashboard's rows share.
    assert sql.count("`teamster-332318.m.dim_students` AS `students`") == 3
    assert _moments(sql)["m.dim_students"] == {START}
    assert all(len(at) == 1 for at in _moments(sql).values())


# A cell SQL that reads the fact a second time, as a filter on its sections.
_TWICE = (
    "FROM  m.fct_s  AS `scores`\n"
    "INNER JOIN (SELECT DISTINCT `again`.section_key FROM  m.fct_s  AS `again`) "
    "AS `seen` ON `seen`.section_key = `scores`.section_key"
)


def test_cube_side_through_joins_wraps_every_read_of_the_fact(duck):
    _joined_tables(duck)
    ex = _JoinEx(cells_from=_TWICE)

    run = _joined_run(duck, ex=ex)
    whole, _ = _joined_cells(duck, keep=False, ex=ex)
    kept, sql = _joined_cells(duck, ex=ex)

    # Each read keeps its own alias around the same keyed subquery.
    assert (
        sql.count("(SELECT `scores`.* FROM `teamster-332318.m.fct_s` AS `scores`") == 2
    )
    assert ") AS `again`" in sql and ") AS `scores`" in sql
    assert whole == run
    assert kept == {("{}", "X"): pytest.approx(0.75)}


def test_cube_side_through_joins_refuses_a_read_of_the_fact_it_cannot_place():
    # The second read has no moment, so the pattern misses it; left as is,
    # it would read every row on one side only.
    grain = _joined_grain()
    sides = _joined_sides(JOINED_CFG, JOINED, frozenset())
    ex = _JoinEx(cells_from=_TWICE)
    pinned = (
        ex.at(ex.cube_sql(pipeline.cell_query("v", JOINED, {})), BUILD.end).sql
        + "\nJOIN `teamster-332318.m.fct_s` AS `third` ON TRUE"
    )
    path = formula.Path(grain, formula.path_joins(grain, sides.cube_rows_sql))

    with pytest.raises(
        formula.NotCompared,
        match="Cube's SQL reads m.fct_s in a form the rewrite does not know",
    ):
        formula.rewrite_cube_sql(
            pinned, [grain.table], grain.columns, [False] * 3, keep=True,
            path=path,
        )  # fmt: skip


def test_cube_side_reads_the_hops_as_the_run_s_cube_rows_read_them():
    # The hops are copied from the row SQL `matched_ctes` reads, not expanded
    # again, so they match it by construction and bill nothing new.
    sides = _joined_sides(JOINED_CFG, JOINED, frozenset())
    moved = datetime(2026, 10, 1, tzinfo=timezone.utc)
    sides = replace(
        sides,
        cube_rows_sql=repin(sides.cube_rows_sql, ["m.dim_students"], BUILD.end, moved),
    )
    grain = _joined_grain()

    body = formula.cube_side_sql(
        JOINED_CFG, JOINED, [{}], BUILD, ex=_JoinEx(), sides=sides,
        tables=[grain.table], grain=grain, keep=False,
    )  # fmt: skip

    assert (
        "LEFT JOIN `teamster-332318.m.dim_students` AS `students` FOR SYSTEM_TIME "
        f"AS OF TIMESTAMP '{utc_literal(moved)}'"
    ) in body


def test_cube_self_check_through_a_join_that_repeats_a_student_differs(duck):
    # Student 2's key sits twice in the students dim, so the subquery repeats
    # score 2 where Cube's cell SQL, which never joins the students, does not.
    _joined_tables(duck, students=[*STUDENTS, (32, 2)])

    run = _joined_run(duck)
    whole, _ = _joined_cells(duck, keep=False)
    kept, _ = _joined_cells(duck)
    check = _verdicts(
        [_cell(dashboard=0.425, cube=run[("{}", "X")])],
        [_dash("{}", "X", 0.75)],
        [_cube("{}", "X", kept[("{}", "X")])],
        cube_self=[_cube("{}", "X", whole[("{}", "X")])],
    )

    assert whole != run
    assert check.not_compared == {formula.REWRITE_DIFFERS: [REF]}


def test_cube_side_keys_a_date_grain_on_a_joined_dim_as_a_date(duck):
    # The item's day is a TIMESTAMP 1 join from the fact; the reconcile keys
    # it by its DATE, so the subquery must too.
    daily = replace(
        JOINED,
        rows=RowSpec(
            grain=[ColumnPair("student", "lea"), ColumnPair("day", "day")],
            values=[ColumnPair("score", "score_c")],
        ),
    )
    _joined_tables(duck)

    kept, _ = _joined_cells(duck, daily, replace(JOINED_CFG, time_dimension="day"))

    # 1, 2 and 5 match by student and day; 5's item differs, but the item
    # is no grain member here.
    assert kept == {("{}", "X"): pytest.approx((0.5 + 1.0 + 0.2) / 3)}


def test_path_joins_refuse_a_table_on_the_path_read_live():
    # An external table is read live, with no moment: the rewrite cannot
    # place it as the run read it, so it refuses rather than guess.
    grain = formula.fact_grain(
        f"SELECT `admins`.aid `v__item` FROM  m.fct_s  AS `scores`\n{_JOINS}",
        "v",
        ["item"],
        ["m.fct_s"],
    )
    pinned = (
        f"SELECT `admins`.aid `v__item` FROM `teamster-332318.m.fct_s` AS `scores` "
        f"FOR SYSTEM_TIME AS OF TIMESTAMP '{END}'\n"
        "LEFT JOIN  m.dim_admins  AS `admins` "
        "ON `admins`.admin_key = `scores`.admin_key"
    )

    with pytest.raises(
        formula.NotCompared,
        match="Cube's SQL reads m.dim_admins in a form the rewrite does not know",
    ):
        formula.path_joins(grain, pinned)


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


def test_a_check_keeps_its_version_and_an_unversioned_one_reads_as_0():
    data = _checked()

    assert data["version"] == formula.CHECK_VERSION
    assert formula.Check.from_json(data).version == formula.CHECK_VERSION
    del data["version"]
    assert formula.Check.from_json(data).version == 0


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


# The run.json of the result `_keep_two_cells` keeps with no formula check,
# pinned byte for byte: a run with no check saves no `origin`. Its `.txt` suffix
# keeps the commit hook's JSON formatter from rewriting the pinned bytes.
NO_CHECK_RUN = Path(__file__).parent / "fixtures" / "run_no_formula_check.json.txt"


def _keep_two_cells(cache, check=None):
    """`_keep_result` plus a differing cell no unmatched row lies in."""
    held = _keep_result(cache, check)
    kept = latest.read_all(held, CFG.fact)["mastery"]
    free = pipeline.Cell(
        "mastery", "{}", "abbreviation=Y", 0.8, 0.3, "differs", (("abbreviation", "Y"),)
    )
    sides = pipeline.Sides.from_json(kept.data)
    sides.cells.append(free)
    data = {**kept.data, **sides.to_json()}
    latest.write(held, "mastery", replace(kept, data=data))
    return held


def test_compose_tags_the_cells_the_formula_check_filed(tmp_path):
    cache = tmp_path / "cache"
    _, run_json = _compose(cache, _keep_two_cells(cache, _checked()))

    cells = {c["key"]: c for c in json.loads(run_json.read_text())["diff_cells"]}
    assert cells["abbreviation=X"]["kind"] == "formula"
    assert cells["abbreviation=X"]["origin"] == "formula check"
    assert cells["abbreviation=Y"]["kind"] == "formula"
    assert "origin" not in cells["abbreviation=Y"]


def test_a_run_with_no_formula_check_saves_as_before_origins(tmp_path):
    cache = tmp_path / "cache"
    _, run_json = _compose(cache, _keep_two_cells(cache))

    assert run_json.read_text() == NO_CHECK_RUN.read_text()
    assert '"origin"' not in run_json.read_text()


@pytest.mark.parametrize(
    "check",
    [
        {"fingerprint": "fp1"},
        {"fingerprint": "fp1", "formula": [["{}"]]},
        {"fingerprint": "fp1", "formula": 3},
        ["fp1"],
        # Its cells read, but not the rest: `sort` could not reuse it, so a
        # compose does not file it either.
        {**_checked(), "not_compared": []},
        {**_checked(), "coverage": None},
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


def _joined_plan(duck, monkeypatch, cube, ex=None, students=STUDENTS):
    """`plan` and `run_job` over the toy DDI, the run's rows saved as
    `compare` saves them; the run's cell reads 0.425 on the dashboard and
    `cube` on Cube."""
    planned = replace(JOINED, confirmed=True, decimals=2)
    cfg = replace(JOINED_CFG, comparisons=[planned])
    ex = ex or _JoinEx()
    monkeypatch.setattr(pipeline, "Expand", lambda *a, **k: ex)
    monkeypatch.setattr(
        pipeline,
        "row_sides",
        lambda cfg, comparison, **k: _joined_sides(cfg, comparison, frozenset()),
    )
    _joined_tables(duck, students=students)
    wh = _PlanWh(duck)
    table = table_id("v", BUILD, "mastery")
    duck.rows("DROP TABLE IF EXISTS __joined")
    sides = _joined_sides(cfg, planned, frozenset())
    for statement in compare.save_script(cfg, planned, sides, table_sql(table), None):
        duck.rows(statement)
    wh.labels[table] = labels(
        "v", BUILD, "mastery", pipeline.checkpoint_fingerprint(planned, FPS["mastery"])
    )
    run = replace(_plan_run(), diff_cells=[_cell(dashboard=0.425, cube=cube)])

    job = formula.plan(
        cfg, run, planned, fingerprint="fp", wh=wh, cube=None,
        prepared=Prepared(schools=set()),
    )  # fmt: skip
    assert isinstance(job, formula.Job)
    return job, formula.run_job(job, planned, wh)


def test_plan_follows_cube_s_joins_and_leaves_row_causes_to_coverage(duck, monkeypatch):
    # The toy DDI: each side's cell moves by rows the other lacks (0.425 and
    # 0.52); on matched rows, keyed through Cube's joins, both read 0.75.
    job, check = _joined_plan(duck, monkeypatch, 0.52)

    assert "LEFT JOIN `teamster-332318.m.dim_students` AS `students`" in job.sql["cube"]
    # The fan-out guard is priced and run with the rest.
    assert set(job.sql) == {
        "dashboard", "cube", "dashboard_self", "cube_self", "cube_fanout",
    }  # fmt: skip
    assert check.coverage == [REF] and check.not_compared == {}


def test_plan_refuses_a_join_that_repeats_fact_rows_a_measure_hides(duck, monkeypatch):
    # Student 2's key sits twice in the students dim. A distinct count does
    # not move when score 2 repeats, so the self-check reproduces the run's
    # cell; the row counts tell the repeat.
    ex = _JoinEx(measure="COUNT(DISTINCT `scores`.score)")

    job, check = _joined_plan(
        duck, monkeypatch, 5, ex=ex, students=[*STUDENTS, (32, 2)]
    )

    assert [r["value"] for r in duck.rows(job.sql["cube_self"])] == [5]
    assert check.not_compared == {formula.FANS_OUT: [REF]}
    assert formula.ran(check)


def test_plan_says_cube_refused_when_cube_refuses_its_sql(duck, offline, monkeypatch):
    def refused(query, rows=False):
        raise CubeRefusal("the compiled query reads another fact")

    monkeypatch.setattr(offline, "cube_sql", refused)

    check, _ = _plan(duck, _plan_run())

    assert check.not_compared == {formula.CUBE_REFUSED: [REF]}


def test_plan_says_unbuilt_on_an_error_no_reason_names(
    duck, offline, monkeypatch, capsys
):
    def broken(query, rows=False):
        raise RuntimeError("a bug in the SQL builder")

    monkeypatch.setattr(offline, "cube_sql", broken)

    check, wh = _plan(duck, _plan_run())

    assert check.not_compared == {formula.UNBUILT: [REF]}
    assert check.formula == [] and check.coverage == [] and wh.ran == []
    assert (
        "Formula check of mastery not built: "
        "RuntimeError('a bug in the SQL builder')" in capsys.readouterr().out
    )


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
