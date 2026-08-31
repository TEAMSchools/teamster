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
from dlt.sources.sql_database import remove_nullability_adapter
from dlt.sources.sql_database.helpers import table_rows
from sqlalchemy import BigInteger, Float, Numeric
from sqlalchemy.sql.sqltypes import _AbstractInterval
from sqlalchemy.types import TypeEngine

from teamster.libraries.dlt.probe import (
    ProbeSignatureConfig,
    ProbeTable,
    probe_signature,
)

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


def _asset_key(code_location: str, table_name: str) -> AssetKey:
    """The asset key for one Focus table (single source of truth).

    The translator, the sensor's asset selection, and the sensor's RunRequest all
    route through this. The dbt `focus_dlt` source's `asset_key` meta must match
    this shape or the dbt-source -> dlt-asset lineage breaks.
    """
    return AssetKey([code_location, "dlt", FOCUS_SOURCE_NAME, table_name])


def build_focus_dlt_pipeline(code_location: str) -> dlt.Pipeline:
    """The shared BigQuery pipeline for one district's Focus source.

    Used by the assets factory (loads) and by the intraday sensor (baseline
    reads via sync_destination + resource state).

    `autodetect_schema=True` is load-bearing: paired with
    `loader_file_format="parquet"` it is what lets a `replace` table whose source
    went to 0 rows truncate successfully (#4733).
    """
    return pipeline(
        pipeline_name=FOCUS_SOURCE_NAME,
        destination=bigquery(autodetect_schema=True),
        dataset_name=f"dagster_{code_location}_dlt_{FOCUS_SOURCE_NAME}",
        progress=LogCollector(dump_system_stats=False),
    )


class FocusDltConfig(Config):
    """Run config for the Focus dlt op.

    `probe` present (intraday sensor): the sensor already probed and gated —
    load exactly the run's asset selection, persisting the passed signatures.
    `probe` absent (04:00 schedule / manual launch): full refresh — probe the
    selection once, then load it all unconditionally with fresh baselines.

    `refresh` is unset on every scheduled run. It exists for the one-time
    migration that recreates already-populated tables so they gain the
    `_dlt_id` / `_dlt_load_id` columns — BigQuery refuses to add REQUIRED
    columns to an existing table, so they must be dropped and reloaded
    (`drop_resources`, #4740).
    """

    probe: dict[str, ProbeSignatureConfig] | None = None
    refresh: str | None = None


class FocusDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=_asset_key(self.code_location, data.resource.name),
            deps=[],
        )

        return asset_spec.merge_attributes(kinds={"postgresql"})


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


def widen_unbounded_numeric_adapter(col_type: TypeEngine) -> TypeEngine:
    """Give unbounded Postgres ``numeric`` an explicit precision and scale.

    Unbounded ``numeric`` reflects as ``precision=None``, which dlt renders as
    ``decimal128(38, 9)``. pyarrow then refuses to rescale any value needing
    more than 9 decimal places, and the extract dies with
    ``Rescaling Decimal value would cause data loss`` —
    ``student_gpa_calculated.weighted_gpa`` is the first Focus column to hit it.
    It also overflowed ``decimal128(38, 18)``, so it carries more than 18
    decimal places: Focus stores an unrounded division result.

    ``(76, 38)`` is the destination ceiling, not a tuning choice. dlt maps
    precision above 38 to ``decimal256``, and BigQuery declares exactly
    ``wei_precision=(76, 38)`` — BIGNUMERIC. Nothing wider exists to fall back
    to. Postgres ``numeric`` scale is unbounded in principle, so a future column
    could still overflow this; rounding in the query would be the only fix left.

    ``Numeric(76, 38)`` maps to BigQuery BIGNUMERIC, not NUMERIC, so a dbt
    staging model over an affected table should ``cast(col as numeric)`` to keep
    contracts on NUMERIC. That retype is why the migration in #5080 reloaded
    every table once: ``replace`` cannot change a column's type in place, so
    200 already-loaded NUMERIC columns needed recreating.

    ``Float`` subclasses ``Numeric`` and also reflects ``precision=None``, so it
    is returned untouched — otherwise every ``double precision`` column would
    land as BIGNUMERIC. The guard now covers all 79 tables in the source.
    (Illuminate's ``unbounded_numeric_adapter`` omits that guard; it has no
    float columns reaching this path today.)
    """
    if isinstance(col_type, Float):
        return col_type

    if isinstance(col_type, Numeric) and col_type.precision is None:
        # ponytail: destination maximum, chosen because Focus is unreachable
        # from CI so the real scale cannot be measured. Narrow it once a loaded
        # value can be inspected in BigQuery.
        return Numeric(precision=76, scale=38)

    return col_type


def _widening_type_adapter(col_type: TypeEngine) -> TypeEngine | None:
    """Both Focus type adapters, applied to every table in the source."""
    return interval_to_microseconds_adapter(widen_unbounded_numeric_adapter(col_type))


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
            type_adapter_callback=_widening_type_adapter,
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
    signature: dict | None = None,
) -> DltResource:
    """Build one full-replace dlt resource for a Focus table.

    Drives the exported ``table_rows`` generator (via `_focus_table_items`)
    rather than wrapping ``sql_table``, so the resource can append
    ``dlt.mark.materialize_table_schema()`` when the source yielded no data. A
    table with 0 rows otherwise produces nothing dlt can act on, normalize drops
    the package, and BigQuery never gets a table — leaving no target for a dbt
    staging model (#4740). Same ``table_rows`` pattern as
    ``libraries/dlt/powerschool/``.

    When `signature` is given it is written to the resource's dlt state WITH the
    load, becoming the baseline the next sensor tick compares against. It is
    written here, inside the extracted resource, because dlt commits state only
    from resources that reached the load package — a write from the source body
    or after the load never round-trips. `parallelized=True` is compatible with
    `resource_state` writes; what breaks is nesting a DltResource inside a
    parallelized resource, which this does not do.
    """

    @dlt.resource(name=table_name, write_disposition="replace", parallelized=True)
    def _focus_table() -> Iterator:
        if signature is not None:
            dlt.current.resource_state()["signature"] = signature

        yield from _focus_table_items(
            sql_database_credentials=sql_database_credentials,
            table_name=table_name,
            db_schema=db_schema,
        )

    return _focus_table


@dlt.source(name=FOCUS_SOURCE_NAME)
def build_focus_source(
    sql_database_credentials: ConnectionStringCredentials,
    tables: list[ProbeTable],
    signatures: dict[str, dict] | None = None,
    db_schema: str | None = FOCUS_DB_SCHEMA,
) -> Iterator:
    """One resource per table. The source name must stay `focus` — it is the dlt
    schema name the destination's stored schema and state are keyed on."""
    signatures = signatures or {}

    for table in tables:
        yield _build_focus_resource(
            sql_database_credentials=sql_database_credentials,
            table_name=table.name,
            db_schema=db_schema,
            signature=signatures.get(table.name),
        )


def build_focus_dlt_assets(
    sql_database_credentials: ConnectionStringCredentials,
    code_location: str,
    tables: list[ProbeTable],
    op_tags: dict[str, object] | None = None,
):
    """Build ONE two-mode @dlt_assets over all Focus tables.

    The selection decision belongs to the caller: the intraday sensor probes,
    gates, and passes per-table signatures via run config (`probe`); the 04:00
    schedule and manual launches pass no config and get an unconditional full
    refresh. In both modes the op runs the pipeline over a source narrowed to the
    run's asset selection — a full `replace` per table — persisting each table's
    signature to dlt resource_state WITH the load, so failures self-heal: the old
    baseline survives and the table re-selects next tick. See
    docs/superpowers/specs/2026-08-10-focus-dlt-probe-gated-sync-design.md.
    """
    if op_tags is None:
        op_tags = {}

    dlt_pipeline = build_focus_dlt_pipeline(code_location)
    translator = FocusDagsterDltTranslator(code_location)
    tables_by_key = {_asset_key(code_location, t.name): t for t in tables}

    @dlt_assets(
        # The full source only defines the asset specs; the op runs a narrowed
        # one.
        dlt_source=build_focus_source(
            sql_database_credentials=sql_database_credentials,
            tables=tables,
        ),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__{FOCUS_SOURCE_NAME}",
        dagster_dlt_translator=translator,
        group_name=FOCUS_SOURCE_NAME,
        pool=f"dlt_{FOCUS_SOURCE_NAME}_{code_location}",
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

        # Diagnostic knob, same as PowerSchool's: a `dlt_extract_workers` run tag
        # caps dlt's extract concurrency. Absent tag -> leave dlt's default (5).
        # Uses `dlt_config` (the module-level accessor imported above), NOT
        # `dlt.config` — `dlt` is the resource parameter here, so `.config` would
        # resolve to `DagsterDltResource`, which has no `config` attribute
        # (AttributeError). See libraries/dlt/CLAUDE.md.
        extract_workers_tag = context.run.tags.get("dlt_extract_workers")
        if extract_workers_tag is not None:
            workers = int(extract_workers_tag)
            dlt_config["extract.workers"] = workers
            context.log.info(f"dlt extract workers capped at {workers}")

        selected = [
            tables_by_key[key]
            for key in context.selected_asset_keys
            if key in tables_by_key
        ]

        if config.probe is not None:
            # Sensor mode: the sensor probed and gated already — persist its
            # signatures with the load, no re-probe.
            signatures: dict[str, dict] = {
                name: {"count": sig.count, "max_cursor": sig.max_cursor}
                for name, sig in config.probe.items()
            }
            context.log.info(f"focus sensor-selected load: {sorted(signatures)}")
        else:
            # Full-refresh mode (04:00 schedule / manual launch): load the whole
            # selection unconditionally. Probe FIRST so fresh baseline signatures
            # persist WITH the load — dlt commits state only from extracted
            # resources, so a post-load write would not round-trip.
            engine = sa.create_engine(
                sql_database_credentials.to_native_representation()
            )
            try:
                with engine.connect() as connection:
                    signatures = {
                        table.name: probe_signature(
                            connection, table.name, table.cursor_column
                        )
                        for table in selected
                    }
            finally:
                engine.dispose()

            context.log.info(f"focus full-refresh load: {sorted(signatures)}")

        # Stream dlt's periodic extract/normalize/load progress into the Dagster
        # event log. The factory-built collector defaults to logger="stdout"
        # (step-pod compute logs only), which went dark for one table at a time
        # before and would now go dark for the whole multi-table load.
        dlt_pipeline.collector = LogCollector(
            logger=context.log, log_period=30.0, dump_system_stats=False
        )

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

        yield from dlt.run(
            context=context,
            dlt_source=build_focus_source(
                sql_database_credentials=sql_database_credentials,
                tables=selected,
                signatures=signatures,
            ),
            dlt_pipeline=dlt_pipeline,
            dagster_dlt_translator=translator,
            **run_kwargs,
        )

    return _assets
