from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import TableInfo, as_of, pin_clock

FIXTURES = Path(__file__).parent / "fixtures"
TS = datetime(2026, 10, 22, 19, 0, 0, tzinfo=timezone.utc)
CLAUSE = "FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 19:00:00+00:00'"


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
    sql = (FIXTURES / "cube_compiled.sql").read_text()
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
        "AS `locations` FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 20:44:04+00:00'"
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
    assert "date(timestamp '2026-10-22 19:00:00+00:00', 'America/New_York')" in (
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
        == "date(timestamp '2026-10-22 19:00:00+00:00', 'America/New_York')"
    )
    assert (
        pin_clock("CURRENT_TIMESTAMP()", TS) == "timestamp '2026-10-22 19:00:00+00:00'"
    )
    assert (
        pin_clock("Current_Datetime(\n    'UTC'\n)", TS)
        == "datetime(timestamp '2026-10-22 19:00:00+00:00', 'UTC')"
    )
    assert (
        pin_clock("current_date ()", TS)
        == "date(timestamp '2026-10-22 19:00:00+00:00')"
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

    assert "TIMESTAMP '2026-10-22 19:00:00+00:00'" in result.sql


def test_naive_datetime_is_refused():
    with pytest.raises(ValueError, match="naive"):
        pin_clock("current_timestamp()", datetime(2026, 10, 22, 19, 0, 0))
