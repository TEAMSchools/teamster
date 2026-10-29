from datetime import datetime, timedelta, timezone

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import JOB_ID, CostCapError, ViewHistoryError, Warehouse
from google.api_core.exceptions import BadRequest

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
    assert "INTERVAL 3 DAY" in sql


def _history_answers(client, answers):
    real = client.query
    it = iter(answers)

    def query(sql, job_config=None):
        job = real(sql, job_config)
        if not (job_config and job_config.dry_run):
            job._rows = next(it)
        return job

    client.query = query


def test_view_history_widens_from_3_to_30_to_180_days():
    table = FakeTable(modified=TS + timedelta(days=1))
    client = FakeClient(table)
    _history_answers(
        client, [[], [], [{"query": "create view `p`.`ds`.`v` as select old"}]]
    )
    wh = Warehouse(client=client)

    assert wh.view_sql_as_of("ds", "v", TS) == "select old"
    sqls = [s for s, dry in client.queries if not dry]
    assert ["INTERVAL 3 DAY" in sqls[0], "INTERVAL 30 DAY" in sqls[1]] == [True] * 2
    assert "INTERVAL 180 DAY" in sqls[2]


def test_view_history_found_in_30_days_skips_the_whole_retention():
    table = FakeTable(modified=TS + timedelta(days=1))
    client = FakeClient(table)
    _history_answers(
        client, [[], [{"query": "create view `p`.`ds`.`v` as select old"}]]
    )
    wh = Warehouse(client=client)

    assert wh.view_sql_as_of("ds", "v", TS) == "select old"
    sqls = [s for s, dry in client.queries if not dry]
    assert len(sqls) == 2
    assert "INTERVAL 30 DAY" in sqls[1]


def test_view_history_is_read_once_per_view_and_moment():
    table = FakeTable(modified=TS + timedelta(days=1))
    client = FakeClient(table, rows=[{"query": "create view `p`.`ds`.`v` as select 1"}])
    wh = Warehouse(client=client)

    wh.view_sql_as_of("ds", "v", TS)
    wh.view_sql_as_of("ds", "v", TS)

    assert len(client.queries) == 1
    wh.view_sql_as_of("ds", "v", TS + timedelta(seconds=1))
    assert len(client.queries) == 2


def test_view_history_serves_an_earlier_moment_after_the_job_started():
    table = FakeTable(modified=TS + timedelta(days=1))
    job = {
        "query": "create view `p`.`ds`.`v` as select 1",
        "start_time": TS - timedelta(days=4),
    }
    client = FakeClient(table, rows=[job])
    wh = Warehouse(client=client)

    wh.view_sql_as_of("ds", "v", TS)
    assert wh.view_sql_as_of("ds", "v", TS - timedelta(seconds=12)) == "select 1"
    assert len(client.queries) == 1
    # Before the job started, it was not the view's definition.
    wh.view_sql_as_of("ds", "v", TS - timedelta(days=5))
    assert len(client.queries) > 1


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


class LimitClient(FakeClient):
    """Refuses a query over its `maximum_bytes_billed`, as BigQuery does."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.limits = []

    def query(self, sql, job_config=None):
        limit = getattr(job_config, "maximum_bytes_billed", None)
        self.limits.append(limit)
        job = super().query(sql, job_config)
        if limit is not None and self.nbytes > int(limit):

            def refuse():
                raise BadRequest(
                    "over", errors=[{"reason": "bytesBilledLimitExceeded"}]
                )

            job.result = refuse
        else:
            job.total_bytes_billed = self.nbytes
        return job


def test_rows_under_a_cap_bills_at_most_what_is_left_with_no_dry_run(tmp_path):
    client = LimitClient(rows=[{"a": 1}], nbytes=int(1.0 / 6.25 * TIB))
    wh = Warehouse(client=client)
    wh.configure_local(tmp_path, daily_cap=3.0)

    with wh.budget(2.0):
        assert wh.rows("select 1") == [{"a": 1}]
        # The run's $2.00 is tighter than the day's $3.00, then $1.00 is left.
        wh.rows("select 2")

    assert not any(dry for _, dry in client.queries)
    assert [int(n) for n in client.limits] == [
        int(2.0 / 6.25 * TIB),
        int(1.0 / 6.25 * TIB),
    ]
    assert wh.spent_today() == pytest.approx(2.0, abs=0.001)


def test_a_query_over_what_is_left_is_refused_by_bigquery_and_counts_nothing(
    tmp_path,
):
    client = LimitClient(rows=[{"a": 1}], nbytes=10 * TIB)
    wh = Warehouse(client=client)
    wh.configure_local(tmp_path, daily_cap=3.0)

    with pytest.raises(CostCapError, match=r"\$3\.00 left under the \$3\.00 daily"):
        wh.rows("select 1")
    assert wh.spent_today() == 0.0


def test_nothing_left_under_a_cap_refuses_before_any_query():
    client = LimitClient(rows=[{"a": 1}])
    wh = Warehouse(client=client)

    with pytest.raises(CostCapError, match=r"nothing is left under the \$0\.00 cap"):
        with wh.budget(0.0):
            wh.rows("select 1")
    assert client.queries == []


def test_a_relation_is_looked_up_once():
    calls = []

    class Client(FakeClient):
        def get_table(self, ref):
            calls.append(ref)
            return super().get_table(ref)

    wh = Warehouse(client=Client(FakeTable("VIEW", "select 1", modified=TS)))
    wh.table("ds", "v")
    wh.table("ds", "v")
    wh.view_sql_as_of("ds", "v", TS + timedelta(hours=1))

    assert calls == ["teamster-332318.ds.v"]


def test_view_sql_drops_trailing_semicolon():
    table = FakeTable(view_query="select 1;\n", modified=TS - timedelta(days=1))
    wh = Warehouse(client=FakeClient(table))

    assert wh.view_sql_as_of("ds", "v", TS) == "select 1"


# --- spend controls: view cache on disk, daily cap, billed bytes --------------

JOB = {
    "query": "create view `p`.`ds`.`v` as select old",
    "start_time": TS - timedelta(days=30),
}


def _changed_view_client(rows):
    return FakeClient(
        FakeTable(view_query="select new", modified=TS + timedelta(days=2)), rows=rows
    )


def _history_reads(client):
    return [s for s, dry in client.queries if not dry and "JOBS_BY_PROJECT" in s]


def test_a_found_view_version_is_reused_by_the_next_run(tmp_path):
    first = _changed_view_client([JOB])
    wh = Warehouse(client=first)
    wh.configure_local(tmp_path, None)
    assert wh.view_sql_as_of("ds", "v", TS) == "select old"

    second = _changed_view_client([])
    wh2 = Warehouse(client=second)
    wh2.configure_local(tmp_path, None)
    assert wh2.view_sql_as_of("ds", "v", TS - timedelta(days=1)) == "select old"
    assert _history_reads(second) == []


def test_a_later_moment_scans_only_the_days_after_the_cached_span(tmp_path):
    wh = Warehouse(client=_changed_view_client([JOB]))
    wh.configure_local(tmp_path, None)
    wh.view_sql_as_of("ds", "v", TS)

    later = _changed_view_client([])
    wh2 = Warehouse(client=later)
    wh2.configure_local(tmp_path, None)
    assert wh2.view_sql_as_of("ds", "v", TS + timedelta(hours=6)) == "select old"
    (sql,) = _history_reads(later)
    assert "creation_time >= TIMESTAMP '2026-10-22 19:00:00.000000+00:00'" in sql
    assert "INTERVAL" not in sql


def test_a_newer_version_in_the_new_days_wins(tmp_path):
    wh = Warehouse(client=_changed_view_client([JOB]))
    wh.configure_local(tmp_path, None)
    wh.view_sql_as_of("ds", "v", TS)

    newer = {
        "query": "create view `p`.`ds`.`v` as select newer",
        "start_time": TS + timedelta(hours=1),
    }
    wh2 = Warehouse(client=_changed_view_client([newer]))
    wh2.configure_local(tmp_path, None)
    assert wh2.view_sql_as_of("ds", "v", TS + timedelta(hours=6)) == "select newer"


def test_the_daily_cap_spans_runs_and_counts_no_refused_query(tmp_path):
    half = int(0.6 / 6.25 * TIB)  # $0.60 a query
    a = Warehouse(client=FakeClient(nbytes=half))
    a.configure_local(tmp_path, 1.0)
    a.price("select 1")

    b = Warehouse(client=FakeClient(nbytes=half))
    b.configure_local(tmp_path, 1.0)
    with pytest.raises(CostCapError, match="today.*\\$1.00 daily cap"):
        b.price("select 2")
    small = Warehouse(client=FakeClient(nbytes=int(0.3 / 6.25 * TIB)))
    small.configure_local(tmp_path, 1.0)
    small.price("select 3")  # $0.60 + $0.30 fits: the refused $0.60 was not counted


def test_estimate_does_not_count_against_the_daily_cap(tmp_path):
    client = FakeClient(nbytes=int(2.0 / 6.25 * TIB))  # $2.00, over both caps
    wh = Warehouse(client=client)
    wh.configure_local(tmp_path, 1.0)

    with wh.budget(1.0):
        assert wh.estimate("select 1") == pytest.approx(2.0, abs=0.001)
        assert wh.spent == 0.0
    assert wh.spent_today() == 0.0
    assert client.queries == [("select 1", True)]


def test_billed_bytes_replace_the_estimate_after_a_query_runs(tmp_path):
    client = FakeClient(rows=[{"x": 1}], nbytes=int(1.0 / 6.25 * TIB))
    real = client.query

    def query(sql, job_config=None):
        job = real(sql, job_config)
        if not (job_config and job_config.dry_run):
            job.total_bytes_billed = int(0.25 / 6.25 * TIB)
        return job

    client.query = query
    wh = Warehouse(client=client)
    wh.configure_local(tmp_path, 10.0)
    with wh.budget(5.0):
        wh.rows("select 1")
        assert wh.spent == pytest.approx(0.25, abs=0.001)
    assert wh.spent_today() == pytest.approx(0.25, abs=0.001)


def test_refuse_past_caps_counts_nothing_and_names_the_cap(tmp_path):
    wh = Warehouse(client=FakeClient())
    with wh.budget(1.0):
        wh.refuse_past_caps(0.9)
        with pytest.raises(CostCapError, match=r"\$1\.00 cap"):
            wh.refuse_past_caps(1.1)
        assert wh.spent == 0.0

    wh.configure_local(tmp_path, daily_cap=0.5)
    with pytest.raises(CostCapError, match="daily cap"):
        wh.refuse_past_caps(0.6)


def test_rows_can_bound_a_query_s_run_time():
    configs = []

    class Client(FakeClient):
        def query(self, sql, job_config=None):
            configs.append(job_config)
            return super().query(sql, job_config)

    wh = Warehouse(client=Client())
    wh.rows("select 1")
    wh.rows("select 2", timeout_s=90)

    assert configs[0] is None
    assert int(configs[1].job_timeout_ms) == 90_000 and not configs[1].dry_run


def test_the_spend_ledger_can_live_apart_from_the_cache(tmp_path):
    ledger = tmp_path / "default"
    wh = Warehouse(client=FakeClient(nbytes=TIB // 100))
    wh.configure_local(tmp_path / "copy", daily_cap=3.0, ledger_dir=ledger)

    wh.price("select 1")

    assert (ledger / "spend.json").exists()
    assert not (tmp_path / "copy" / "spend.json").exists()
    other = Warehouse(client=FakeClient())
    other.configure_local(tmp_path / "another", daily_cap=3.0, ledger_dir=ledger)
    assert other.spent_today() == pytest.approx(6.25 / 100)


def test_a_failed_query_carries_its_job_id():
    class Failing(FakeClient):
        def query(self, sql, job_config=None):
            job = super().query(sql, job_config)
            setattr(job, JOB_ID, "job-1")

            def boom():
                raise BadRequest("Bad int64 value: 12345")

            job.result = boom
            return job

    with pytest.raises(BadRequest) as caught:
        Warehouse(client=Failing()).rows("select 1")

    assert getattr(caught.value, JOB_ID) == "job-1"


def test_a_query_that_fails_mid_run_still_counts_what_it_billed(tmp_path):
    class Client(FakeClient):
        def query(self, sql, job_config=None):
            job = super().query(sql, job_config)

            def boom():
                raise BadRequest("timed out", errors=[{"reason": "timeout"}])

            def reload():
                job.total_bytes_billed = int(0.5 / 6.25 * TIB)

            job.result, job.reload = boom, reload
            return job

    wh = Warehouse(client=Client())
    wh.configure_local(tmp_path, daily_cap=3.0)

    with pytest.raises(BadRequest), wh.budget(2.0):
        wh.rows("select 1", timeout_s=1)

    assert wh.spent_today() == pytest.approx(0.5, abs=0.001)
