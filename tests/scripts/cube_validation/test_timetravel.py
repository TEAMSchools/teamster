from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import (
    TableInfo,
    as_of,
    closing_paren,
    pin_clock,
    repin,
)

FIXTURES = Path(__file__).parent / "fixtures"
TS = datetime(2026, 10, 22, 19, 0, 0, tzinfo=timezone.utc)
CLAUSE = "FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 19:00:00.000000+00:00'"


class FakeCatalog:
    def __init__(self, tables: dict[str, TableInfo]):
        self._tables = tables

    def table(self, dataset: str, name: str) -> TableInfo:
        return self._tables[f"{dataset}.{name}"]

    def view_sql_as_of(self, dataset: str, name: str, ts: datetime) -> str:
        view_sql = self._tables[f"{dataset}.{name}"].view_sql
        assert view_sql is not None
        return view_sql


def test_cube_table_gets_alias_before_clause():
    sql = (FIXTURES / "cube_compiled.sql.txt").read_text()
    names = [
        "fct_student_attendance_enrollment_daily",
        "dim_student_enrollments",
        "dim_locations",
        "dim_dates",
        "dim_regions",
    ]
    catalog = FakeCatalog(
        {f"kipptaf_marts.{n}": TableInfo("TABLE", None) for n in names}
    )
    ts = datetime(2026, 10, 22, 20, 44, 4, tzinfo=timezone.utc)

    result = as_of(sql, ts, catalog)

    assert "`teamster-332318.kipptaf_marts.dim_locations`" in result.sql
    assert (
        "AS `locations` FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 20:44:04.000000+00:00'"
    ) in result.sql
    assert result.sql.count("FOR SYSTEM_TIME") == 5
    assert result.tables == frozenset(f"kipptaf_marts.{n}" for n in names)
    assert result.live == frozenset()


def test_view_is_inlined_recursively():
    sql = "SELECT 1 FROM  kipptaf_marts.dim_locations  AS `locations`"
    catalog = FakeCatalog(
        {
            "kipptaf_marts.dim_locations": TableInfo(
                "VIEW",
                "select * from `teamster-332318`.`kipptaf_google_sheets`.`stg_x` as x",
            ),
            "kipptaf_google_sheets.stg_x": TableInfo("TABLE", None),
        }
    )

    result = as_of(sql, TS, catalog)

    assert result.sql == (
        "SELECT 1 FROM  (select * from "
        f"`teamster-332318.kipptaf_google_sheets.stg_x` as x {CLAUSE}"
        ") AS `locations`"
    )
    assert result.tables == frozenset({"kipptaf_google_sheets.stg_x"})


def test_quoted_ref_is_left_alone():
    body = (FIXTURES / "view_union.sql").read_text()
    catalog = FakeCatalog(
        {"kippmiami_focus.stg_focus__schools": TableInfo("TABLE", None)}
    )

    result = as_of(body, TS, catalog)

    assert "'''`teamster-332318.kippmiami_focus.int_focus__schools`'''" in result.sql
    assert result.tables == frozenset({"kippmiami_focus.stg_focus__schools"})
    assert (
        "`teamster-332318.kippmiami_focus.stg_focus__schools` as s " + CLAUSE
    ) in result.sql
    assert "current_date" not in result.sql
    assert "date(timestamp '2026-10-22 19:00:00.000000+00:00', 'America/New_York')" in (
        result.sql
    )


def test_external_table_is_read_live():
    sql = "SELECT 1 FROM ds.sheet AS `s`"
    catalog = FakeCatalog({"ds.sheet": TableInfo("EXTERNAL", None)})

    result = as_of(sql, TS, catalog)

    assert result.sql == sql
    assert result.live == frozenset({"ds.sheet"})
    assert result.tables == frozenset()
    assert "FOR SYSTEM_TIME" not in result.sql


def test_pin_clock_variants():
    assert (
        pin_clock("current_date('America/New_York')", TS)
        == "date(timestamp '2026-10-22 19:00:00.000000+00:00', 'America/New_York')"
    )
    assert (
        pin_clock("CURRENT_TIMESTAMP()", TS)
        == "timestamp '2026-10-22 19:00:00.000000+00:00'"
    )
    assert (
        pin_clock("Current_Datetime(\n    'UTC'\n)", TS)
        == "datetime(timestamp '2026-10-22 19:00:00.000000+00:00', 'UTC')"
    )
    assert (
        pin_clock("current_date ()", TS)
        == "date(timestamp '2026-10-22 19:00:00.000000+00:00')"
    )


def test_view_depth_limit():
    catalog = FakeCatalog(
        {
            "ds.loop": TableInfo(
                "VIEW", "select * from `teamster-332318`.`ds`.`loop` as l"
            )
        }
    )

    with pytest.raises(ValueError, match="depth"):
        as_of("select * from ds.loop as `l`", TS, catalog)


def test_timestamp_is_normalized_to_utc():
    eastern = timezone(timedelta(hours=-4))
    catalog = FakeCatalog({"ds.t": TableInfo("TABLE", None)})

    result = as_of(
        "from ds.t as `t`", datetime(2026, 10, 22, 15, 0, 0, tzinfo=eastern), catalog
    )

    assert "TIMESTAMP '2026-10-22 19:00:00.000000+00:00'" in result.sql


def test_naive_datetime_is_refused():
    with pytest.raises(ValueError, match="naive"):
        pin_clock("current_timestamp()", datetime(2026, 10, 22, 19, 0, 0))


PINNED = "timestamp '2026-10-22 19:00:00.000000+00:00'"


def test_pin_clock_bare_forms():
    assert pin_clock("current_date", TS) == f"date({PINNED})"
    assert pin_clock("CURRENT_TIMESTAMP", TS) == PINNED
    assert pin_clock("current_datetime", TS) == f"datetime({PINNED})"
    assert pin_clock("current_time", TS) == f"time({PINNED})"
    assert pin_clock("current_time('UTC')", TS) == f"time({PINNED}, 'UTC')"


def test_pin_clock_nested_paren_zone():
    assert (
        pin_clock("current_date(concat('a','b'))", TS)
        == f"date({PINNED}, concat('a','b'))"
    )
    assert pin_clock("current_date(lower('X')) > d", TS) == (
        f"date({PINNED}, lower('X')) > d"
    )


def test_pin_clock_unbalanced_is_refused():
    with pytest.raises(ValueError, match="unbalanced"):
        pin_clock("current_date(lower('X')", TS)


def test_clock_inside_inlined_view_is_pinned():
    catalog = FakeCatalog(
        {
            "ds.v": TableInfo(
                "VIEW",
                "select current_date as d, current_timestamp() as t "
                "from `teamster-332318`.`ds`.`base` as b",
            ),
            "ds.base": TableInfo("TABLE", None),
        }
    )

    result = as_of("select * from ds.v as `v`", TS, catalog)

    assert "current_" not in result.sql.lower()
    assert f"date({PINNED}) as d" in result.sql
    assert f"{PINNED} as t" in result.sql


def test_dbt_ref_after_join_and_unaliased_ref():
    catalog = FakeCatalog(
        {"ds.a": TableInfo("TABLE", None), "ds.b": TableInfo("TABLE", None)}
    )
    sql = "select 1 from `teamster-332318`.`ds`.`a` join `teamster-332318`.`ds`.`b` as b on true"

    result = as_of(sql, TS, catalog)

    assert f"`teamster-332318.ds.a` {CLAUSE} join" in result.sql
    assert f"`teamster-332318.ds.b` as b {CLAUSE} on" in result.sql
    assert result.tables == frozenset({"ds.a", "ds.b"})


def test_comma_joined_from_list_is_refused():
    catalog = FakeCatalog(
        {"d.t": TableInfo("TABLE", None), "d.u": TableInfo("TABLE", None)}
    )

    with pytest.raises(ValueError, match="comma"):
        as_of("select 1 from d.t as `x`, d.u as `y`", TS, catalog)


def test_unaliased_cube_style_ref_is_refused():
    catalog = FakeCatalog({"d.t": TableInfo("TABLE", None)})

    with pytest.raises(ValueError, match="not recognized"):
        as_of("select 1 from d.t x", TS, catalog)

    with pytest.raises(ValueError, match="not recognized"):
        as_of("select 1 from a join d.t on true", TS, catalog)


def test_extract_from_is_not_a_table_ref():
    catalog = FakeCatalog({})

    result = as_of("select extract(year from s.d) from unnest([1]) as x", TS, catalog)

    assert result.tables == frozenset()


def test_repin_moves_only_the_named_tables():
    catalog = FakeCatalog(
        {
            "ds.a": TableInfo("TABLE", None),
            "ds.b": TableInfo("TABLE", None),
        }
    )
    sql = (
        "SELECT 1 FROM ds.a AS `x` JOIN `teamster-332318`.`ds`.`a` "
        "JOIN `teamster-332318`.`ds`.`b` as bb"
    )
    later = TS + timedelta(seconds=12)
    rewritten = as_of(sql, later, catalog).sql

    out = repin(rewritten, ["ds.a"], later, TS)

    assert out.count(CLAUSE) == 2
    assert "`teamster-332318.ds.a` AS `x` " + CLAUSE in out
    assert (
        "`teamster-332318.ds.b` as bb FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 19:00:12"
        in out
    )


def test_closing_paren_skips_quotes_backticks_and_escapes():
    sql = "f(a, ')', `x)`, 'it\\'s)', g(1)) tail"
    assert sql[closing_paren(sql, 1) + 1 :] == " tail"
