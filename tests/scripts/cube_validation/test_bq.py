from datetime import datetime, timedelta, timezone

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import CostCapError, ViewHistoryError, Warehouse

TS = datetime(2026, 10, 22, 19, 0, 0, tzinfo=timezone.utc)
TIB = 2**40


class FakeTable:
    def __init__(self, table_type="VIEW", view_query="select 1", modified=TS):
        self.table_type = table_type
        self.view_query = view_query
        self.modified = modified


class FakeJob:
    def __init__(self, rows, nbytes):
        self._rows = rows
        self.total_bytes_processed = nbytes

    def result(self):
        return self._rows


class FakeClient:
    def __init__(self, table=None, rows=None, nbytes=0):
        self._table = table
        self._rows = rows or []
        self.nbytes = nbytes
        self.queries: list[tuple[str, bool]] = []

    def get_table(self, ref):
        if self._table is None:
            raise KeyError(ref)

        return self._table

    def query(self, sql, job_config=None):
        dry = bool(job_config and job_config.dry_run)
        self.queries.append((sql, dry))

        return FakeJob([] if dry else self._rows, self.nbytes)


def test_view_sql_uses_current_when_unchanged():
    table = FakeTable(view_query="select current", modified=TS - timedelta(days=1))
    wh = Warehouse(client=FakeClient(table))

    assert wh.view_sql_as_of("ds", "v", TS) == "select current"
    assert wh._client.queries == []


def test_view_sql_uses_create_view_job_when_changed_after():
    table = FakeTable(view_query="select new", modified=TS + timedelta(days=1))
    job_sql = (
        "CREATE OR REPLACE VIEW `p`.`ds`.`v` OPTIONS(description='a (b) as c') "
        "AS select old from t"
    )
    client = FakeClient(table, rows=[{"query": job_sql}])
    wh = Warehouse(client=client)

    assert wh.view_sql_as_of("ds", "v", TS) == "select old from t"
    sql = client.queries[0][0]
    assert "CREATE_VIEW" in sql
    assert "creation_time < TIMESTAMP '2026-10-22 19:00:00.000000+00:00'" in sql
    assert "INTERVAL 180 DAY" in sql


def test_view_sql_without_options():
    table = FakeTable(modified=TS + timedelta(days=1))
    job_sql = "create view `p`.`ds`.`v` as\nselect 1 as a"
    wh = Warehouse(client=FakeClient(table, rows=[{"query": job_sql}]))

    assert wh.view_sql_as_of("ds", "v", TS) == "select 1 as a"


def test_view_sql_skips_dbt_query_comment():
    table = FakeTable(modified=TS + timedelta(days=1))
    job_sql = '/* {"app": "dbt", "node_id": "model.x"} */\ncreate or replace view `p`.`ds`.`v` as select 1'
    wh = Warehouse(client=FakeClient(table, rows=[{"query": job_sql}]))

    assert wh.view_sql_as_of("ds", "v", TS) == "select 1"


def test_view_history_missing_is_refused():
    table = FakeTable(modified=TS + timedelta(days=1))
    wh = Warehouse(client=FakeClient(table, rows=[]))

    with pytest.raises(ViewHistoryError, match="ds.v"):
        wh.view_sql_as_of("ds", "v", TS)


def test_table_kind_maps_bigquery_types():
    wh = Warehouse(client=FakeClient(FakeTable("EXTERNAL", None)))
    assert wh.table("ds", "t").kind == "EXTERNAL"

    wh = Warehouse(client=FakeClient(FakeTable("VIEW", "select 1")))
    info = wh.table("ds", "v")
    assert (info.kind, info.view_sql) == ("VIEW", "select 1")

    wh = Warehouse(client=FakeClient(FakeTable("TABLE", None)))
    assert wh.table("ds", "t").kind == "TABLE"


def test_price_is_dry_run_at_6_25_per_tib():
    client = FakeClient(nbytes=2 * TIB)
    wh = Warehouse(client=client)

    assert wh.price("select 1") == pytest.approx(12.5)
    assert client.queries == [("select 1", True)]


def test_rows_returns_dicts():
    wh = Warehouse(client=FakeClient(rows=[{"a": 1}]))

    assert wh.rows("select 1") == [{"a": 1}]


def test_budget_stops_past_cap():
    nbytes = int(3 / 6.25 * TIB)
    wh = Warehouse(client=FakeClient(nbytes=nbytes))

    with pytest.raises(CostCapError), wh.budget(5.0):
        wh.price("select 1")
        wh.price("select 2")


def test_budget_guards_rows_before_running():
    client = FakeClient(rows=[{"a": 1}], nbytes=10 * TIB)
    wh = Warehouse(client=client)

    with pytest.raises(CostCapError), wh.budget(5.0):
        wh.rows("select 1")

    assert all(dry for _, dry in client.queries)


def test_view_sql_drops_trailing_semicolon():
    table = FakeTable(view_query="select 1;\n", modified=TS - timedelta(days=1))
    wh = Warehouse(client=FakeClient(table))

    assert wh.view_sql_as_of("ds", "v", TS) == "select 1"
