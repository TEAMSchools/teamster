"""The Focus resource materializes a never-loaded table's schema (#4740).

A configured Focus table with no rows produced nothing at all before, so dlt
dropped the load package and BigQuery never got a table. The resource now yields
`materialize_table_schema()` in that case, which creates the table from the
reflected schema.

sqlite stands in for Focus Postgres: the item shapes `table_rows` yields and the
files dlt normalizes from them are backend-generic, and the Codespace cannot
reach Focus (IP allowlist).

These tests exercise a real `dlt.pipeline().extract()` + `.normalize()` against
a `filesystem` destination (no extra deps, no live server) rather than iterating
the built resource directly with `list(resource())`. dlt's `DltResource.__iter__`
unconditionally unwraps `DataItemWithMeta` (and empty-list markers like
`MaterializedEmptyList`) down to their `.data` payload before handing items to
the caller (`PipeIterator._get_source_item`, dlt 1.29.1) — so a naive
`list(resource())` can never observe the marker objects themselves, for ANY
`dlt.resource`-wrapped generator, regardless of what it yields. The markers only
have effect inside the real extract/normalize machinery, which is what these
tests exercise.
"""

import pathlib
import tempfile
from collections.abc import Iterator

import dlt
import pytest
import sqlalchemy as sa
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.pipeline.pipeline import Pipeline

from teamster.libraries.dlt.focus.assets import build_focus_source


@pytest.fixture(name="sqlite_url")
def fixture_sqlite_url() -> Iterator[str]:
    """A sqlite file with a `referrals` table whose row count the test sets."""
    with tempfile.TemporaryDirectory() as tmp:
        yield f"sqlite:///{pathlib.Path(tmp) / 'focus.db'}"


def _seed(url: str, rows: int) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "create table referrals (referral_id integer not null, comment text)"
            )
        )
        for i in range(rows):
            conn.execute(sa.text("insert into referrals values (:i, 'c')"), {"i": i})
    engine.dispose()


def _extract_and_normalize(url: str, pipelines_dir: pathlib.Path) -> Pipeline:
    """Build the real Focus source and run it through extract + normalize.

    `filesystem` needs no extra dependency and no live server, unlike `duckdb`
    (not installed in this venv) or `bigquery` (needs GCP credentials) — but it
    still exercises the same `Extractor`/normalizer code path that
    `HintsMeta`/`materialize_table_schema()` are designed for, unlike direct
    resource iteration.
    """
    source = build_focus_source(
        sql_database_credentials=ConnectionStringCredentials(url),
        table_name="referrals",
        db_schema=None,
    )

    pipeline = dlt.pipeline(
        pipeline_name="focus_materialize_empty_test",
        destination="filesystem",
        dataset_name="focus_materialize_empty_test",
        pipelines_dir=str(pipelines_dir),
    )
    pipeline.extract(source)
    pipeline.normalize()

    return pipeline


def test_empty_table_yields_materialize_marker(
    sqlite_url: str, tmp_path: pathlib.Path
) -> None:
    """A 0-row table must still normalize into a job, or the table is created.

    Without `dlt.mark.materialize_table_schema()`, a resource that produced no
    items is dropped entirely — `referrals` would be absent from
    `row_counts`, exactly the prod bug (#4740).
    """
    _seed(sqlite_url, rows=0)

    pipeline = _extract_and_normalize(sqlite_url, tmp_path)

    row_counts = pipeline.last_trace.last_normalize_info.row_counts
    assert row_counts.get("referrals") == 0, (
        "a 0-row table must still produce a normalized job so the table is created"
    )


def test_populated_table_yields_no_materialize_marker(
    sqlite_url: str, tmp_path: pathlib.Path
) -> None:
    _seed(sqlite_url, rows=3)

    pipeline = _extract_and_normalize(sqlite_url, tmp_path)

    row_counts = pipeline.last_trace.last_normalize_info.row_counts
    assert row_counts.get("referrals") == 3


def test_reflection_hints_precede_the_marker(
    sqlite_url: str, tmp_path: pathlib.Path
) -> None:
    """The hints marker must come first, or the created table has no columns.

    dlt registers the reflected columns from the `HintsMeta` item; a
    `materialize_table_schema()` that arrived before it would create a table
    holding only the `_dlt_*` columns.
    """
    _seed(sqlite_url, rows=0)

    pipeline = _extract_and_normalize(sqlite_url, tmp_path)

    columns = pipeline.default_schema.tables["referrals"]["columns"]
    assert {"referral_id", "comment"} <= set(columns), (
        "the reflected source columns must be registered, not just dlt's"
        " internal _dlt_* columns"
    )
