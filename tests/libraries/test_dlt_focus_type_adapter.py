"""Unit tests for the Focus dlt type adapters (issues #4676, #5021).

Focus added an `interval` column (`time_limit`) to `public.gradebook_assignments`,
which dlt cannot map: the reflected type matches none of the branches in
`sqla_col_to_column_schema`, so the column gets no `data_type`, the PyArrow
backend infers `duration[us]` from the `timedelta` values, and dlt raises
`UnsupportedArrowTypeException`.

`interval_to_microseconds_adapter` declares `BigInteger` for those columns so
dlt casts the duration to int64 microseconds instead.

`widen_unbounded_numeric_adapter` covers the second case: unbounded Postgres
`numeric` reflects as `precision=None`, dlt renders it `decimal128(38, 9)`, and
pyarrow refuses any value needing more than 9 decimal places
(`student_gpa_calculated.weighted_gpa`). It is opt-in per table, so these tests
also pin that the opt-in routes to the right adapter.
"""

from datetime import timedelta
from typing import Any

import pytest
from dagster_dlt.constants import META_KEY_SOURCE
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.libs.pyarrow import (
    UnsupportedArrowTypeException,
    py_arrow_to_table_schema_columns,
)
from dlt.common.schema.typing import TTableSchemaColumns
from dlt.sources.sql_database import remove_nullability_adapter
from dlt.sources.sql_database.arrow_helpers import row_tuples_to_arrow
from dlt.sources.sql_database.schema_types import (
    TTypeAdapter,
    sqla_col_to_column_schema,
)
from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, INTERVAL
from sqlalchemy.sql import sqltypes

from teamster.libraries.dlt.focus.assets import (
    build_focus_dlt_assets,
    interval_to_microseconds_adapter,
    widen_unbounded_numeric_adapter,
)
from teamster.libraries.dlt.probe import ProbeTable


def _gradebook_assignments_table() -> Table:
    """Minimal stand-in for the reflected Focus `gradebook_assignments` table."""
    return Table(
        "gradebook_assignments",
        MetaData(),
        Column("assignment_id", Integer, nullable=False),
        Column("title", String, nullable=True),
        Column("time_limit", INTERVAL(), nullable=True),
    )


def _reflect_columns(
    table: Table, type_adapter_callback: TTypeAdapter | None = None
) -> TTableSchemaColumns:
    """Reflect a table into dlt column schemas the way `sql_database` does."""
    columns: TTableSchemaColumns = {}

    for col in table.columns:
        column_schema = sqla_col_to_column_schema(
            col, "full_with_precision", type_adapter_callback=type_adapter_callback
        )

        assert column_schema is not None, f"no column schema reflected for {col.name}"

        columns[col.name] = column_schema

    return columns


def test_adapter_maps_postgres_interval_to_bigint():
    assert isinstance(interval_to_microseconds_adapter(INTERVAL()), BigInteger)


def test_adapter_maps_generic_interval_to_bigint():
    """`postgresql.INTERVAL` and `sqltypes.Interval` share only `_AbstractInterval`."""
    assert isinstance(interval_to_microseconds_adapter(sqltypes.Interval()), BigInteger)


@pytest.mark.parametrize(
    "col_type", [Integer(), String(), sqltypes.Numeric(38, 9), sqltypes.DateTime()]
)
def test_adapter_passes_other_types_through_unchanged(col_type):
    assert interval_to_microseconds_adapter(col_type) is col_type


def test_factory_builds_a_source_with_the_table_named_resource():
    """Guard the wiring the translator depends on.

    The asset key comes from `data.resource.name`, so a resource named anything
    else silently changes every Focus asset key.
    """
    assets = build_focus_dlt_assets(
        sql_database_credentials=ConnectionStringCredentials(
            "postgresql+psycopg://localhost:5432/focus"
        ),
        code_location="kippmiami",
        tables=[ProbeTable(name="gradebook_assignments", cursor_column="updated_at")],
    )

    dlt_source = next(iter(assets.specs)).metadata[META_KEY_SOURCE]

    assert list(dlt_source.resources) == ["gradebook_assignments"]
    assert dlt_source.name == "focus"
    assert next(iter(assets.specs)).key.path == [
        "kippmiami",
        "dlt",
        "focus",
        "gradebook_assignments",
    ]


def test_extract_invokes_both_adapters(monkeypatch, tmp_path):
    """The adapters must reach `table_rows`, not merely exist.

    Uses sqlite (the Codespace cannot reach Focus) and records each adapter call,
    so a factory that stops passing one fails here.
    """
    import sqlalchemy as sa

    from teamster.libraries.dlt.focus import assets as focus_assets

    url = f"sqlite:///{tmp_path / 'focus.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("create table t (id integer not null, note text)"))
    engine.dispose()

    type_calls: list[object] = []
    table_calls: list[object] = []

    original_type_adapter = focus_assets.interval_to_microseconds_adapter
    original_table_adapter = focus_assets.remove_nullability_adapter

    def spy_type_adapter(col_type):
        type_calls.append(col_type)
        return original_type_adapter(col_type)

    def spy_table_adapter(table):
        table_calls.append(table)
        return original_table_adapter(table)

    monkeypatch.setattr(
        focus_assets, "interval_to_microseconds_adapter", spy_type_adapter
    )
    monkeypatch.setattr(focus_assets, "remove_nullability_adapter", spy_table_adapter)

    resource = focus_assets._build_focus_resource(
        sql_database_credentials=ConnectionStringCredentials(url),
        table_name="t",
        db_schema=None,
    )
    list(resource())

    assert type_calls, "type_adapter_callback was not passed to table_rows"
    assert table_calls, "table_adapter_callback was not passed to table_rows"


def test_reflection_settings_reach_table_rows(monkeypatch):
    """Pin the extract settings, not just the adapters.

    `reflection_level="full_with_precision"` is what preserves Postgres
    precision and scale; a silent regression to `"minimal"` would widen or
    truncate every Focus column with nothing else failing. `backend="pyarrow"`
    is what the interval adapter and the parquet loader assume.
    """
    from teamster.libraries.dlt.focus import assets as focus_assets

    captured: dict[str, Any] = {}

    def spy_table_rows(**kwargs):
        captured.update(kwargs)
        return iter(())

    monkeypatch.setattr(focus_assets, "table_rows", spy_table_rows)

    resource = focus_assets._build_focus_resource(
        sql_database_credentials=ConnectionStringCredentials("sqlite://"),
        table_name="gradebook_assignments",
        db_schema="public",
    )
    list(resource())

    assert captured["reflection_level"] == "full_with_precision"
    assert captured["backend"] == "pyarrow"
    assert captured["table_adapter_callback"] is remove_nullability_adapter
    assert captured["type_adapter_callback"] is interval_to_microseconds_adapter
    assert captured["table"] == "gradebook_assignments"
    assert captured["metadata"].schema == "public"

    # table_rows takes no defaults but `table_loader_class`; a dropped kwarg
    # would silently change extract behavior
    assert captured["incremental"] is None
    assert captured["query_adapter_callback"] is None
    assert captured["resolve_foreign_keys"] is False


def test_interval_column_without_adapter_reproduces_prod_failure():
    """Regression guard: this is the exact prod error the adapter fixes."""
    columns = _reflect_columns(_gradebook_assignments_table())

    # dlt cannot type the interval column, so it carries no `data_type` hint
    assert columns["time_limit"].get("data_type") is None

    arrow_table = row_tuples_to_arrow(
        [(1, "Quiz 1", timedelta(minutes=45))], columns=columns, tz="UTC"
    )

    assert str(arrow_table.schema.field("time_limit").type) == "duration[us]"

    with pytest.raises(UnsupportedArrowTypeException):
        py_arrow_to_table_schema_columns(arrow_table.schema)


def test_interval_column_with_adapter_loads_as_bigint_microseconds():
    columns = _reflect_columns(
        _gradebook_assignments_table(),
        type_adapter_callback=interval_to_microseconds_adapter,
    )

    assert columns["time_limit"].get("data_type") == "bigint"

    arrow_table = row_tuples_to_arrow(
        [
            (1, "Quiz 1", timedelta(minutes=45)),
            (2, "Quiz 2", None),
            # `Time` would silently corrupt these two; `bigint` holds them exactly
            (3, "Take-home", timedelta(hours=48)),
            (4, "Adjustment", timedelta(minutes=-30)),
        ],
        columns=columns,
        tz="UTC",
    )

    assert str(arrow_table.schema.field("time_limit").type) == "int64"

    # the schema computation that raised in prod now succeeds
    dlt_columns = py_arrow_to_table_schema_columns(arrow_table.schema)

    assert dlt_columns["time_limit"].get("data_type") == "bigint"

    assert arrow_table.column("time_limit").to_pylist() == [
        45 * 60 * 1_000_000,
        None,
        48 * 60 * 60 * 1_000_000,
        -30 * 60 * 1_000_000,
    ]


def test_widen_unbounded_numeric_adapter_only_touches_unbounded_numeric():
    """Unbounded `numeric` gains a scale; bounded numeric and floats do not."""
    widened = widen_unbounded_numeric_adapter(sqltypes.Numeric())

    assert isinstance(widened, sqltypes.Numeric)
    assert (widened.precision, widened.scale) == (38, 18)

    bounded = sqltypes.Numeric(precision=10, scale=2)
    assert widen_unbounded_numeric_adapter(bounded) is bounded

    # Float subclasses Numeric and also reflects precision=None. Without the
    # guard every `double precision` column would land as BIGNUMERIC.
    double = DOUBLE_PRECISION()
    assert widen_unbounded_numeric_adapter(double) is double


def test_widening_type_adapter_keeps_the_interval_mapping():
    """Opting into numeric widening must not drop the interval mapping."""
    from teamster.libraries.dlt.focus import assets as focus_assets

    assert isinstance(focus_assets._widening_type_adapter(INTERVAL()), BigInteger)

    widened = focus_assets._widening_type_adapter(sqltypes.Numeric())
    assert isinstance(widened, sqltypes.Numeric)
    assert (widened.precision, widened.scale) == (38, 18)


def test_widen_numeric_flag_selects_the_type_adapter(monkeypatch):
    """The per-table opt-in is what reaches `table_rows`, not a source-wide flag."""
    from teamster.libraries.dlt.focus import assets as focus_assets

    captured: dict[str, Any] = {}

    def spy_table_rows(**kwargs):
        captured[kwargs["table"]] = kwargs["type_adapter_callback"]
        return iter(())

    monkeypatch.setattr(focus_assets, "table_rows", spy_table_rows)

    for table_name, widen in (("plain", False), ("widened", True)):
        resource = focus_assets._build_focus_resource(
            sql_database_credentials=ConnectionStringCredentials("sqlite://"),
            table_name=table_name,
            db_schema="public",
            widen_numeric=widen,
        )
        list(resource())

    assert captured["plain"] is interval_to_microseconds_adapter
    assert captured["widened"] is focus_assets._widening_type_adapter
