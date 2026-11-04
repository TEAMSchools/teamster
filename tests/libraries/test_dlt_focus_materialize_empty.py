"""The Focus resource materializes a never-loaded table's schema (#4740).

A configured Focus table with no rows produced nothing at all before, so dlt
dropped the load package and BigQuery never got a table. The resource now yields
`materialize_table_schema()` in that case, which creates the table from the
reflected schema.

sqlite stands in for Focus Postgres: the item shapes `table_rows` yields and the
files dlt normalizes from them are backend-generic, and the Codespace cannot
reach Focus (IP allowlist).

These tests call `_focus_table_items` directly — a plain generator, not the
`@dlt.resource`-wrapped one — because dlt's `DltResource.__iter__`
unconditionally unwraps `DataItemWithMeta` (and flattens empty-list markers
like `MaterializedEmptyList`) down to their `.data` payload before a caller
ever sees them (`PipeIterator._get_source_item`, dlt 1.29.1). A naive
`list(resource())` can never observe the marker objects themselves, for ANY
`dlt.resource`-wrapped generator — so the marker/ordering assertions below have
to run against the plain generator directly.
"""

import pathlib
import tempfile
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.extract.extractors import MaterializedEmptyList
from dlt.extract.items import DataItemWithMeta

from teamster.libraries.dlt.focus.assets import _focus_table_items


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


def _items(url: str) -> list:
    return list(
        _focus_table_items(
            sql_database_credentials=ConnectionStringCredentials(url),
            table_name="referrals",
            db_schema=None,
        )
    )


def test_empty_table_yields_materialize_marker(sqlite_url: str) -> None:
    _seed(sqlite_url, rows=0)

    items = _items(sqlite_url)

    assert isinstance(items[-1], MaterializedEmptyList), (
        "a 0-row table must end with materialize_table_schema() so the table is created"
    )


def test_populated_table_yields_no_materialize_marker(sqlite_url: str) -> None:
    _seed(sqlite_url, rows=3)

    items = _items(sqlite_url)

    assert not any(isinstance(i, MaterializedEmptyList) for i in items)

    data_items = [i for i in items if not isinstance(i, DataItemWithMeta)]
    assert [i.num_rows for i in data_items] == [3]


def test_reflection_hints_precede_the_marker(sqlite_url: str) -> None:
    """The hints marker must come first, or the created table has no columns.

    dlt registers the reflected columns from the `HintsMeta` item; a
    `materialize_table_schema()` that arrived before it would create a table
    holding only the `_dlt_*` columns. Asserted by index, not by checking
    `items[0]` alone, so a reordered implementation (marker yielded before the
    hints) fails this test even if it still yields both items.
    """
    _seed(sqlite_url, rows=0)

    items = _items(sqlite_url)

    hints_index = next(
        i for i, item in enumerate(items) if isinstance(item, DataItemWithMeta)
    )
    marker_index = next(
        i for i, item in enumerate(items) if isinstance(item, MaterializedEmptyList)
    )

    assert hints_index < marker_index
    assert type(items[hints_index].meta).__name__ == "HintsMeta"
