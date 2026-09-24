from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from google.cloud import bigquery

from teamster.cube_sandbox import avro, load, snapshot

SNAP = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}


def test_a_complete_load_passes() -> None:
    load.assert_complete(SNAP, {"dim_x": {"a"}})


def test_a_partial_load_is_caught() -> None:
    # The generator writes table by table. A failure partway leaves the
    # sandbox short of the snapshot it was built from, and nothing else
    # notices.
    with pytest.raises(ValueError, match="dim_x.a"):
        load.assert_complete(SNAP, {"dim_x": set()})


class _FakeQueryResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def result(self) -> list[Any]:
        return self._rows


class _FakeQueryClient:
    """Fake standing in for the piece of the BigQuery client `loaded_columns`
    touches: `.query(sql).result()` yielding rows with `table_name` and
    `column_name` attributes, the shape INFORMATION_SCHEMA.COLUMNS returns."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.queries: list[str] = []

    def query(self, sql: str) -> _FakeQueryResult:
        self.queries.append(sql)
        return _FakeQueryResult(self._rows)


def test_loaded_columns_groups_rows_by_table() -> None:
    client = _FakeQueryClient(
        [
            SimpleNamespace(table_name="dim_x", column_name="a"),
            SimpleNamespace(table_name="dim_x", column_name="b"),
            SimpleNamespace(table_name="dim_y", column_name="c"),
        ]
    )

    out = load.loaded_columns(client, "teamster-cube-sandbox", "kipptaf_marts")

    assert out == {"dim_x": {"a", "b"}, "dim_y": {"c"}}
    assert "kipptaf_marts.INFORMATION_SCHEMA.COLUMNS" in client.queries[0]


def test_loaded_columns_empty_result_yields_empty_dict() -> None:
    client = _FakeQueryClient([])
    assert load.loaded_columns(client, "teamster-cube-sandbox", "kipptaf_marts") == {}


class _FakeLoadJob:
    def result(self) -> None:
        return None


class _FakeLoadClient:
    """Fake standing in for the piece of the BigQuery client `load_table`
    touches: `.load_table_from_uri(...)` returning an object with `.result()`.
    Records the call so the test can inspect the job config it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, Any, Any]] = []

    def load_table_from_uri(
        self, source_uris: Any, destination: Any, job_config: Any
    ) -> _FakeLoadJob:
        self.calls.append((source_uris, destination, job_config))
        return _FakeLoadJob()


def test_load_table_uses_avro_logical_types_and_truncate_disposition() -> None:
    # Both details are load-bearing per the brief: without
    # use_avro_logical_types a DATE column lands as INT64, and without
    # WRITE_TRUNCATE a rebuild appends instead of replacing.
    client = _FakeLoadClient()
    schema = avro.bq_schema("dim_x", {"a": {"type": "STRING", "nullable": True}})

    load.load_table(client, "dim_x", "gs://bucket/dim_x.avro", schema)

    assert len(client.calls) == 1
    source_uri, destination, job_config = client.calls[0]
    assert source_uri == "gs://bucket/dim_x.avro"
    assert destination == "teamster-cube-sandbox.kipptaf_marts.dim_x"
    assert job_config.use_avro_logical_types is True
    assert job_config.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert job_config.source_format == bigquery.SourceFormat.AVRO
    assert job_config.schema == schema


class _FakeMainClient:
    """Fake standing in for the full BigQuery client surface `main` touches:
    load_table_from_uri for each table, then one query for the post-load
    check. `rows` controls what the INFORMATION_SCHEMA query reports back,
    independent of what load_table_from_uri was called with, so a test can
    simulate a load that silently landed short."""

    def __init__(self, rows: list[Any], project: str | None = None) -> None:
        self.rows = rows
        self.project = project
        self.load_calls: list[Any] = []

    def load_table_from_uri(
        self, source_uris: Any, destination: Any, job_config: Any
    ) -> _FakeLoadJob:
        self.load_calls.append(destination)
        return _FakeLoadJob()

    def query(self, sql: str) -> _FakeQueryResult:
        return _FakeQueryResult(self.rows)


def test_main_returns_0_when_the_load_matches_the_snapshot(monkeypatch: Any) -> None:
    snap = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}
    monkeypatch.setattr(snapshot, "load", lambda: snap)
    rows = [SimpleNamespace(table_name="dim_x", column_name="a")]
    monkeypatch.setattr(
        bigquery, "Client", lambda project=None: _FakeMainClient(rows, project)
    )

    assert load.main() == 0


def test_main_raises_when_the_load_lands_short(monkeypatch: Any) -> None:
    # Simulates exactly the failure `assert_complete` exists to catch: the
    # generator writes dim_x but a second table's columns never showed up in
    # INFORMATION_SCHEMA, even though load_table_from_uri was "called" for
    # both and neither raised.
    snap = {
        "tables": {
            "dim_x": {"a": {"type": "STRING", "nullable": True}},
            "dim_y": {"b": {"type": "STRING", "nullable": True}},
        }
    }
    monkeypatch.setattr(snapshot, "load", lambda: snap)
    rows = [SimpleNamespace(table_name="dim_x", column_name="a")]
    monkeypatch.setattr(
        bigquery, "Client", lambda project=None: _FakeMainClient(rows, project)
    )

    with pytest.raises(ValueError, match="dim_y.b"):
        load.main()


def test_an_unsafe_project_or_dataset_identifier_is_refused() -> None:
    # INFORMATION_SCHEMA is a path element, so it cannot be passed as a query
    # parameter and the identifiers are interpolated. The bandit suppression
    # on that f-string is only honest if the signature enforces what the call
    # site happens to do.
    class _Client:
        def query(self, sql: str):  # pragma: no cover - must never be reached
            raise AssertionError(f"query should not have run: {sql}")

    for bad in (
        "proj`.`secret",
        "proj; DROP TABLE x",
        "proj.other",
        "",
        "pro ject",
    ):
        with pytest.raises(ValueError, match="unsafe BigQuery"):
            load.loaded_columns(_Client(), bad, load.SANDBOX_DATASET)
        with pytest.raises(ValueError, match="unsafe BigQuery"):
            load.loaded_columns(_Client(), load.SANDBOX_PROJECT, bad)


def test_the_real_project_and_dataset_pass_the_guard() -> None:
    # A guard that rejected the only call site would be worse than none.
    class _Client:
        def query(self, sql: str):
            assert "teamster-cube-sandbox.kipptaf_marts" in sql
            return _Result()

    class _Result:
        def result(self):
            return []

    assert (
        load.loaded_columns(_Client(), load.SANDBOX_PROJECT, load.SANDBOX_DATASET) == {}
    )
