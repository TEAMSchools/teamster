from collections.abc import Iterator
from typing import Any, get_args

import dlt
import sqlalchemy as sa
from dagster import AssetExecutionContext, AssetKey, AssetSpec, Config
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import config as dlt_config
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.runtime.collector import LogCollector
from dlt.common.typing import TRefreshMode
from dlt.destinations import bigquery
from dlt.extract.items import DataItemWithMeta
from dlt.extract.resource import DltResource
from dlt.extract.source import DltSource
from dlt.sources.sql_database import remove_nullability_adapter
from dlt.sources.sql_database.helpers import table_rows
from sqlalchemy import BigInteger
from sqlalchemy.sql.sqltypes import _AbstractInterval
from sqlalchemy.types import TypeEngine

FOCUS_SOURCE_NAME = "focus"
FOCUS_DB_SCHEMA = "public"
FOCUS_CHUNK_SIZE = 50000

REFRESH_MODES = frozenset(get_args(TRefreshMode))
"""dlt's accepted `refresh` values, read from dlt so this cannot drift.

The config field is a plain `str`, not this `Literal`: Dagster's Pythonic config
cannot resolve one (`DagsterInvalidConfigDefinitionError: ... cannot be
resolved`), so the op validates the string against this set instead. Without
that guard dlt treats ANY unrecognized value as `drop_resources`
(`dlt/pipeline/helpers.py::prepare_refresh_source` compares only against
`drop_sources` and `drop_data`), so a typo would silently drop and recreate
every table in the run.
"""


class FocusDltConfig(Config):
    """Run config for the Focus dlt op.

    `refresh` is unset on every scheduled run. It exists for the one-time
    migration that recreates already-populated tables so they gain the
    `_dlt_id` / `_dlt_load_id` columns — BigQuery refuses to add REQUIRED
    columns to an existing table, so they must be dropped and reloaded
    (`drop_resources`, #4740).
    """

    refresh: str | None = None


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
                    data.resource.name,
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
    24 hours or more and negative intervals. int64 microseconds spans roughly
    292,000 years — lossless for any realistic interval, though narrower than
    Postgres ``interval``'s full +/-178,000,000-year range.

    Note the check is ``_AbstractInterval``, the only base shared by
    ``postgresql.INTERVAL`` and ``sqltypes.Interval`` —
    ``isinstance(INTERVAL(), sqltypes.Interval)`` is ``False``.

    See https://dlthub.com/docs/dlt-ecosystem/verified-sources/arrow-pandas#supported-arrow-data-types
    """
    if isinstance(col_type, _AbstractInterval):
        return BigInteger()

    return col_type


def _focus_table_items(
    sql_database_credentials: ConnectionStringCredentials,
    table_name: str,
    db_schema: str | None,
) -> Iterator:
    """Yield one Focus table's items, appending a materialize marker if empty.

    A plain generator (not `@dlt.resource`-wrapped) so tests can iterate the
    real item stream directly — `DltResource.__iter__` unconditionally unwraps
    `DataItemWithMeta` (and flattens empty-list markers like
    `MaterializedEmptyList`) down to their `.data` payload before a caller ever
    sees them (`PipeIterator._get_source_item`, dlt 1.29.1), so a resource built
    from this can never expose the markers themselves via direct iteration.

    The engine is created here, at extract time: the factory that calls this
    runs at module import in the code location, which must not open a
    connection.
    """
    engine = sa.create_engine(sql_database_credentials.to_native_representation())
    try:
        saw_data = False

        for item in table_rows(
            engine=engine,
            table=table_name,
            metadata=sa.MetaData(schema=db_schema),
            chunk_size=FOCUS_CHUNK_SIZE,
            backend="pyarrow",
            incremental=None,
            table_adapter_callback=remove_nullability_adapter,
            reflection_level="full_with_precision",
            backend_kwargs={},
            type_adapter_callback=interval_to_microseconds_adapter,
            included_columns=None,
            excluded_columns=None,
            query_adapter_callback=None,
            resolve_foreign_keys=False,
        ):
            # table_rows opens with a HintsMeta item carrying the reflected
            # schema, then yields arrow tables. Only the latter is data.
            if not isinstance(item, DataItemWithMeta):
                saw_data = True

            yield item

        if not saw_data:
            yield dlt.mark.materialize_table_schema()
    finally:
        engine.dispose()


def _build_focus_resource(
    sql_database_credentials: ConnectionStringCredentials,
    table_name: str,
    db_schema: str | None = FOCUS_DB_SCHEMA,
) -> DltResource:
    """Build one full-replace dlt resource for a Focus table.

    Drives the exported ``table_rows`` generator (via `_focus_table_items`)
    rather than wrapping ``sql_table``, so the resource can append
    ``dlt.mark.materialize_table_schema()`` when the source yielded no data. A
    table with 0 rows otherwise produces nothing dlt can act on, normalize drops
    the package, and BigQuery never gets a table — leaving no target for a dbt
    staging model (#4740). Same ``table_rows`` pattern as
    ``libraries/dlt/powerschool/``.
    """

    @dlt.resource(name=table_name, write_disposition="replace", parallelized=True)
    def _focus_table() -> Iterator:
        yield from _focus_table_items(
            sql_database_credentials=sql_database_credentials,
            table_name=table_name,
            db_schema=db_schema,
        )

    return _focus_table


@dlt.source(name=FOCUS_SOURCE_NAME)
def build_focus_source(
    sql_database_credentials: ConnectionStringCredentials,
    table_name: str,
    db_schema: str | None = FOCUS_DB_SCHEMA,
) -> Iterator:
    """One-resource source. The name must stay `focus` — it is the dlt schema
    name the destination's stored schema and state are keyed on."""
    yield _build_focus_resource(
        sql_database_credentials=sql_database_credentials,
        table_name=table_name,
        db_schema=db_schema,
    )


def build_focus_dlt_assets(
    sql_database_credentials: ConnectionStringCredentials,
    code_location: str,
    table_name: str,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source: DltSource = build_focus_source(
        sql_database_credentials=sql_database_credentials, table_name=table_name
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
    def _assets(
        context: AssetExecutionContext,
        config: FocusDltConfig,
        dlt: DagsterDltResource,
    ) -> Iterator:
        # Both knobs make the arrow data path carry `_dlt_id` / `_dlt_load_id`,
        # which dlt's object path injects as REQUIRED when
        # `materialize_table_schema()` creates an empty table. Without them the
        # first real load into such a table fails with
        # `Field _dlt_load_id is missing in new schema` (#4740). Set here, not at
        # import: each step runs in its own pod, so it cannot leak to another
        # pipeline. NOT `dlt.config` — `dlt` is the resource parameter here.
        dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
        dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

        # loader_file_format="parquet": BigQuery schema autodetection rejects the
        # empty jsonl file dlt writes to truncate a `replace` table whose source
        # went to 0 rows. See `replace` write-disposition in ../CLAUDE.md (#4733).
        run_kwargs: dict[str, Any] = {
            "write_disposition": "replace",
            "loader_file_format": "parquet",
        }

        if config.refresh is not None:
            if config.refresh not in REFRESH_MODES:
                raise ValueError(
                    f"refresh must be one of {sorted(REFRESH_MODES)}, got"
                    f" {config.refresh!r} — dlt would silently treat that as"
                    " drop_resources and recreate every table in this run"
                )

            context.log.info(f"dlt refresh mode: {config.refresh}")
            run_kwargs["refresh"] = config.refresh

        yield from dlt.run(context=context, **run_kwargs)

    return _assets
