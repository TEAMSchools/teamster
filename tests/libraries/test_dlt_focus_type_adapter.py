"""Unit tests for the Focus dlt `interval` type adapter (issue #4676).

Focus added an `interval` column (`time_limit`) to `public.gradebook_assignments`,
which dlt cannot map: the reflected type matches none of the branches in
`sqla_col_to_column_schema`, so the column gets no `data_type`, the PyArrow
backend infers `duration[us]` from the `timedelta` values, and dlt raises
`UnsupportedArrowTypeException`.

`interval_to_microseconds_adapter` declares `BigInteger` for those columns so
dlt casts the duration to int64 microseconds instead.
"""

from datetime import timedelta

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
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.sql import sqltypes

from teamster.libraries.dlt.focus.assets import (
    build_focus_dlt_assets,
    interval_to_microseconds_adapter,
)


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


def test_factory_wires_both_adapters_into_the_dlt_source():
    """Guard the wiring, not just the adapter function.

    Every other test in this module would still pass if `build_focus_dlt_assets`
    dropped `type_adapter_callback=`, since they call the adapter directly. This
    asserts the factory-built source actually carries it. `defer_table_reflect`
    means no connection is opened, so no live Focus database is needed.
    """
    assets = build_focus_dlt_assets(
        sql_database_credentials=ConnectionStringCredentials(
            "postgresql+psycopg://localhost:5432/focus"
        ),
        code_location="kippmiami",
        table_name="gradebook_assignments",
    )

    dlt_source = next(iter(assets.specs)).metadata[META_KEY_SOURCE]
    explicit_args = dlt_source.resources["gradebook_assignments"].explicit_args

    assert explicit_args["type_adapter_callback"] is interval_to_microseconds_adapter

    # the interval adapter must not have displaced the nullability adapter
    assert explicit_args["table_adapter_callback"] is remove_nullability_adapter
    assert explicit_args["reflection_level"] == "full_with_precision"
    assert explicit_args["backend"] == "pyarrow"


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
