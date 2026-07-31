from collections.abc import Iterator

from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import remove_nullability_adapter, sql_database
from sqlalchemy import BigInteger
from sqlalchemy.sql.sqltypes import _AbstractInterval
from sqlalchemy.types import TypeEngine


class FocusDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=AssetKey(
                [
                    self.code_location,
                    "dlt",
                    "focus",
                    data.resource.explicit_args["table"],
                ]
            ),
            deps=[],
        )

        asset_spec = asset_spec.merge_attributes(kinds={"postgresql"})

        return asset_spec


def interval_to_microseconds_adapter(col_type: TypeEngine) -> TypeEngine | None:
    """Map Postgres ``interval`` columns to int64 microseconds.

    Postgres ``interval`` matches none of the branches in dlt's
    ``sqla_col_to_column_schema``, so the reflected column carries no
    ``data_type``, the PyArrow backend infers ``duration[us]`` from the
    ``timedelta`` values, and dlt rejects the load with
    ``UnsupportedArrowTypeException``. Declaring ``BigInteger`` makes dlt cast
    the duration to int64 microseconds instead.

    ``BigInteger`` rather than ``Time``: dlt converts duration to ``time64`` by
    reinterpreting the underlying buffer, which silently corrupts intervals of
    24 hours or more and negative intervals. Microseconds are lossless for any
    interval Postgres can hold.

    Note the check is ``_AbstractInterval``, the only base shared by
    ``postgresql.INTERVAL`` and ``sqltypes.Interval`` —
    ``isinstance(INTERVAL(), sqltypes.Interval)`` is ``False``.

    See https://dlthub.com/docs/dlt-ecosystem/verified-sources/arrow-pandas#supported-arrow-data-types
    """
    if isinstance(col_type, _AbstractInterval):
        return BigInteger()

    return col_type


def build_focus_dlt_assets(
    sql_database_credentials: ConnectionStringCredentials,
    code_location: str,
    table_name: str,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source = sql_database.with_args(name="focus", parallelized=True)(
        credentials=sql_database_credentials,
        schema="public",
        table_names=[table_name],
        defer_table_reflect=True,
        backend="pyarrow",
        reflection_level="full_with_precision",
        table_adapter_callback=remove_nullability_adapter,
        type_adapter_callback=interval_to_microseconds_adapter,
    )

    dlt_pipeline = pipeline(
        pipeline_name="focus",
        destination=bigquery(autodetect_schema=True),
        dataset_name=f"dagster_{code_location}_dlt_focus",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__focus__{table_name}",
        dagster_dlt_translator=FocusDagsterDltTranslator(code_location),
        group_name="focus",
        pool=f"dlt_focus_{code_location}",
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> Iterator:
        yield from dlt.run(context=context, write_disposition="replace")

    return _assets
