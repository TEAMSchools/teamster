from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.cloud import bigquery, storage

from teamster.cube_sandbox import avro, load, snapshot

SNAP = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}


def test_a_complete_load_passes() -> None:
    load.assert_complete(SNAP, {"dim_x": {"a": "STRING"}})


def test_a_partial_load_is_caught() -> None:
    # The generator writes table by table. A failure partway leaves the
    # sandbox short of the snapshot it was built from, and nothing else
    # notices.
    with pytest.raises(ValueError, match="dim_x.a: missing"):
        load.assert_complete(SNAP, {"dim_x": {}})


def test_a_retyped_column_is_caught() -> None:
    # The quiet one. A NUMERIC that lands as FLOAT64 passes any check that
    # compares names, and a kit built on that sandbox learns that money and
    # rate columns are floats — then repoints onto production NUMERICs and
    # starts rounding.
    snap = {"tables": {"dim_x": {"rate": {"type": "NUMERIC", "nullable": True}}}}
    with pytest.raises(ValueError, match="loaded as FLOAT64, snapshot says NUMERIC"):
        load.assert_complete(snap, {"dim_x": {"rate": "FLOAT64"}})


class _FakeQueryResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def result(self) -> list[Any]:
        return self._rows


class _FakeQueryClient:
    """Fake standing in for the piece of the BigQuery client `loaded_schema`
    touches: `.query(sql).result()` yielding rows with `table_name`,
    `column_name` and `data_type` attributes, the shape
    INFORMATION_SCHEMA.COLUMNS returns."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.queries: list[str] = []

    def query(self, sql: str) -> _FakeQueryResult:
        self.queries.append(sql)
        return _FakeQueryResult(self._rows)


def test_loaded_schema_carries_the_declared_types() -> None:
    client = _FakeQueryClient(
        [
            SimpleNamespace(table_name="dim_x", column_name="a", data_type="STRING"),
            SimpleNamespace(table_name="dim_x", column_name="b", data_type="NUMERIC"),
            SimpleNamespace(table_name="dim_y", column_name="c", data_type="DATE"),
        ]
    )

    out = load.loaded_schema(client, "teamster-cube-sandbox", "kipptaf_marts")

    assert out == {
        "dim_x": {"a": "STRING", "b": "NUMERIC"},
        "dim_y": {"c": "DATE"},
    }
    assert "kipptaf_marts.INFORMATION_SCHEMA.COLUMNS" in client.queries[0]


def test_loaded_schema_empty_result_yields_empty_dict() -> None:
    client = _FakeQueryClient([])
    assert load.loaded_schema(client, "teamster-cube-sandbox", "kipptaf_marts") == {}


class _FakeLoadJob:
    def result(self) -> None:
        return None


class _FakeClient:
    """Every piece of the BigQuery client surface the load path touches."""

    def __init__(self, rows: list[Any] | None = None, project: str | None = None):
        self.rows = rows or []
        self.project = project
        self.deleted: list[str] = []
        self.created: list[Any] = []
        self.loads: list[tuple[Any, Any, Any]] = []

    def delete_table(self, table_id: str, not_found_ok: bool = False) -> None:
        self.deleted.append(table_id)

    def create_table(self, table: Any) -> Any:
        self.created.append(table)
        return table

    def load_table_from_uri(
        self, source_uris: Any, destination: Any, job_config: Any
    ) -> _FakeLoadJob:
        self.loads.append((source_uris, destination, job_config))
        return _FakeLoadJob()

    def query(self, sql: str) -> _FakeQueryResult:
        return _FakeQueryResult(self.rows)


def test_create_table_replaces_the_table_with_the_snapshot_schema() -> None:
    # Replace, not create-if-missing: a table left over from an earlier pin
    # carries that pin's columns, and a load into it is measured against the
    # wrong contract.
    client = _FakeClient()
    schema = avro.bq_schema("dim_x", {"a": {"type": "STRING", "nullable": True}})

    load.create_table(client, "dim_x", schema)

    assert client.deleted == ["teamster-cube-sandbox.kipptaf_marts.dim_x"]
    assert len(client.created) == 1
    assert list(client.created[0].schema) == schema


def test_load_table_keeps_the_pre_created_schema() -> None:
    # BigQuery takes an AVRO load's schema from the self-describing file and
    # ignores LoadJobConfig.schema, so the explicit schema has to come from
    # the pre-created table. WRITE_TRUNCATE_DATA keeps that table's schema;
    # WRITE_TRUNCATE would put the Avro-derived one back.
    client = _FakeClient()

    load.load_table(client, "dim_x", "gs://bucket/dim_x.avro")

    assert len(client.loads) == 1
    source_uri, destination, job_config = client.loads[0]
    assert source_uri == "gs://bucket/dim_x.avro"
    assert destination == "teamster-cube-sandbox.kipptaf_marts.dim_x"
    assert job_config.source_format == bigquery.SourceFormat.AVRO
    assert job_config.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE_DATA
    assert job_config.create_disposition == bigquery.CreateDisposition.CREATE_NEVER
    assert job_config.use_avro_logical_types is True
    # Passing one would document a guarantee the API does not give.
    assert job_config.schema is None


class _FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.uploaded: str | None = None

    def upload_from_filename(self, filename: str, content_type: str) -> None:
        self.uploaded = filename


class _FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.blobs: dict[str, _FakeBlob] = {}

    def blob(self, name: str) -> _FakeBlob:
        return self.blobs.setdefault(name, _FakeBlob(name))


class _FakeStorage:
    def __init__(self, project: str | None = None) -> None:
        self.project = project
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, name: str) -> _FakeBucket:
        return self.buckets.setdefault(name, _FakeBucket(name))


def test_upload_stages_the_file_and_returns_its_uri(tmp_path: Path) -> None:
    # main() used to read a gs:// URI nothing ever wrote, so a first real run
    # would have created every table and then failed on a missing object.
    client = _FakeStorage()
    local = tmp_path / "dim_x.avro"
    local.write_bytes(b"avro")

    uri = load.upload(client, local, "teamster-cube-sandbox-staging")

    assert uri == "gs://teamster-cube-sandbox-staging/dim_x.avro"
    assert client.buckets["teamster-cube-sandbox-staging"].blobs[
        "dim_x.avro"
    ].uploaded == str(local)


def _stub_clients(monkeypatch: Any, client: _FakeClient) -> None:
    monkeypatch.setattr(bigquery, "Client", lambda project=None: client)
    monkeypatch.setattr(storage, "Client", lambda project=None: _FakeStorage(project))


def test_main_uploads_creates_loads_and_verifies(
    monkeypatch: Any, tmp_path: Path
) -> None:
    snap = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}
    monkeypatch.setattr(snapshot, "load", lambda: snap)
    (tmp_path / "dim_x.avro").write_bytes(b"avro")
    client = _FakeClient(
        [SimpleNamespace(table_name="dim_x", column_name="a", data_type="STRING")]
    )
    _stub_clients(monkeypatch, client)

    assert load.main(["--avro-dir", str(tmp_path)]) == 0
    assert client.deleted and client.created and client.loads


def test_main_raises_when_a_column_lands_under_the_wrong_type(
    monkeypatch: Any, tmp_path: Path
) -> None:
    # Every load job "succeeded" and nothing raised; the sandbox is simply
    # not the snapshot. This is the only thing that catches it.
    snap = {"tables": {"dim_x": {"a": {"type": "NUMERIC", "nullable": True}}}}
    monkeypatch.setattr(snapshot, "load", lambda: snap)
    (tmp_path / "dim_x.avro").write_bytes(b"avro")
    _stub_clients(
        monkeypatch,
        _FakeClient(
            [SimpleNamespace(table_name="dim_x", column_name="a", data_type="FLOAT64")]
        ),
    )

    with pytest.raises(ValueError, match="loaded as FLOAT64"):
        load.main(["--avro-dir", str(tmp_path)])


def test_main_refuses_to_run_without_generated_avro(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setattr(snapshot, "load", lambda: SNAP)
    _stub_clients(monkeypatch, _FakeClient())

    with pytest.raises(SystemExit, match="no Avro to load"):
        load.main(["--avro-dir", str(tmp_path)])


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
            load.loaded_schema(_Client(), bad, load.SANDBOX_DATASET)
        with pytest.raises(ValueError, match="unsafe BigQuery"):
            load.loaded_schema(_Client(), load.SANDBOX_PROJECT, bad)


def test_the_real_project_and_dataset_pass_the_guard() -> None:
    # A guard that rejected the only call site would be worse than none.
    class _Client:
        def query(self, sql: str):
            assert "teamster-cube-sandbox.kipptaf_marts" in sql
            return _FakeQueryResult([])

    assert (
        load.loaded_schema(_Client(), load.SANDBOX_PROJECT, load.SANDBOX_DATASET) == {}
    )
