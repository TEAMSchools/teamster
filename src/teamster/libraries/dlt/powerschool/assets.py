from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime

import dlt
import sqlalchemy as sa
from dagster import AssetExecutionContext, AssetKey, AssetSpec, Config
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import remove_nullability_adapter
from dlt.sources.sql_database.helpers import table_rows
from sqlalchemy import Float, Numeric
from sqlalchemy.types import TypeEngine

from teamster.libraries.dlt.powerschool.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource

# PowerSchool tables are owned by the `ps` schema. The ODBC pipeline reaches
# them via unqualified raw SQL (Oracle synonym/default-schema resolution), but
# SQLAlchemy reflection needs the owner schema explicitly or it raises
# NoSuchTableError.
ORACLE_SCHEMA = "ps"

# All PowerSchool tables land under one dlt source/pipeline named "powerschool".
# The `sis` asset-key segment mirrors the `powerschool/enrollment/*` namespace.
_SOURCE_NAME = "powerschool"


def _asset_key(code_location: str, table_name: str) -> AssetKey:
    """The asset key for one PowerSchool SIS table (single source of truth).

    The `sis` segment differentiates SIS from the `powerschool/enrollment/*`
    namespace; the dbt `powerschool_dlt` source's `asset_key` meta must match
    this shape or the dbt-source -> dlt-asset lineage breaks.
    """
    return AssetKey([code_location, _SOURCE_NAME, "sis", table_name])


@dataclass(frozen=True)
class PowerSchoolTable:
    """One PowerSchool table's sync config.

    cursor_column None means the table has no change-tracking column and is
    always fully replaced when selected (nightly tier only).
    """

    name: str
    cursor_column: str | None


def probe_signature(
    connection, table_name: str, cursor_column: str | None
) -> dict[str, int | str | None]:
    """Fetch the change signature for a table: total count + max cursor.

    Equality-compared against the stored signature; drift in either value
    (including a cursor regression) triggers a full replace. Tables without a
    cursor column are count-only — the signature still carries
    ``max_cursor: None`` so it compares equal to the run-config round-trip
    shape (which defaults the key to None). Values are JSON-serializable for
    dlt resource state.
    """
    if cursor_column is None:
        (count,) = connection.execute(
            # trunk-ignore(bandit/B608): table name from static YAML config
            sa.text(f"SELECT COUNT(*) FROM {table_name}")
        ).one()

        return {"count": int(count), "max_cursor": None}

    count, max_cursor = connection.execute(
        # trunk-ignore(bandit/B608): table/column names from static YAML config
        sa.text(f"SELECT COUNT(*), MAX({cursor_column}) FROM {table_name}")
    ).one()

    if max_cursor is None:
        max_cursor_value = None
    elif isinstance(max_cursor, (datetime, date)):
        max_cursor_value = max_cursor.isoformat()
    else:
        # Non-temporal cursor (e.g. a numeric change column on a future table);
        # store its string form so the signature stays JSON-serializable.
        max_cursor_value = str(max_cursor)

    # int(count): mirror the JSON-safe-scalar normalization done for max_cursor
    # above (oracledb returns int today, but keep the state doc driver-agnostic).
    return {"count": int(count), "max_cursor": max_cursor_value}


def _compute_changed(
    selected: list[PowerSchoolTable],
    current: dict[str, dict],
    stored: dict[str, dict],
) -> list[PowerSchoolTable]:
    """Select tables whose just-probed signature differs from the stored one.

    Drift in count or max cursor — or a missing stored entry (first tick, or a
    table new to intraday) — selects the table. No-cursor tables carry a
    count-only signature (``max_cursor: None``), so a net row add/remove
    selects them; in-place edits are caught by the nightly full refresh.
    """
    return [
        table for table in selected if current.get(table.name) != stored.get(table.name)
    ]


def _resolve_extract_workers(tag_value: str | None, param: int | None) -> int | None:
    """Resolve the dlt extract worker cap: a per-run tag overrides the
    factory param, which overrides dlt's default (None = leave default)."""
    if tag_value is not None:
        return int(tag_value)
    return param


class ProbeSignatureConfig(Config):
    """One table's probed change signature, passed by the intraday sensor."""

    count: int
    max_cursor: str | None = None


class PowerSchoolDltConfig(Config):
    """Run config selecting the op's mode.

    probe present (intraday sensor): the sensor already probed and gated —
    load exactly the run's asset selection, persisting the passed signatures.
    probe absent (nightly schedule / manual launch): full refresh — probe the
    selection once, then load it all unconditionally with fresh baselines.
    """

    probe: dict[str, ProbeSignatureConfig] | None = None


def build_powerschool_dlt_pipeline(code_location: str) -> dlt.Pipeline:
    """The shared BigQuery pipeline for one district's PowerSchool source.

    Used by the assets factory (loads) and the intraday sensor (baseline
    reads via sync_destination + resource state).
    """
    return dlt.pipeline(
        pipeline_name=_SOURCE_NAME,
        # No `autodetect_schema=True`: oracle_number_adapter +
        # full_with_precision reflection are the authoritative decimal schema
        # (see oracle_number_adapter docstring).
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_{_SOURCE_NAME}",
        progress=LogCollector(dump_system_stats=False),
    )


def oracle_number_adapter(col_type: TypeEngine) -> TypeEngine | None:
    """Keep Oracle NUMBER columns off FLOAT64 in BigQuery.

    Decimal Oracle NUMBER columns can reflect as Float (landing as FLOAT64 —
    float drift on GPA/balance columns) or as unbounded Numeric (landing as
    BIGNUMERIC via dlt's decimal128(38, 9+) default). Pin both to
    Numeric(38, 9), which dlt's BigQuery destination maps to NUMERIC.
    """
    if isinstance(col_type, Float) or (
        isinstance(col_type, Numeric) and col_type.precision is None
    ):
        return Numeric(precision=38, scale=9)
    return col_type


class PowerSchoolDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str) -> None:
        self.code_location = code_location
        super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=_asset_key(self.code_location, data.resource.name),
            deps=[],
        )

        return asset_spec.merge_attributes(kinds={"oracle"})


def _build_resource(
    table: PowerSchoolTable, signature: dict | None, connection_url: str, arraysize: int
):
    """Build one full-replace, parallel-extracted dlt resource for a table.

    When a signature is provided it is persisted to the resource's dlt state
    with the load package, becoming the baseline the next intraday tick
    compares against. Every selected table is passed a signature now: cursor
    tables a count + max-cursor pair, no-cursor tables a count-only signature
    (``max_cursor`` None) whose count is the intraday change gate. A ``None``
    signature persists nothing.

    `parallelized=True` runs each table's extract in its own dlt worker thread.
    The resource does NOT wrap `sql_table` (a `DltResource`) — nesting a resource
    under `parallelized` mangles dlt's per-resource injectable context
    (`ContainerInjectableContextMangled`). Instead it drives the exported
    `table_rows` generator directly (a plain generator, not a resource), which
    accepts the same reflection + Oracle-decimal adapters, so `resource_state`
    writes persist correctly under parallel extract. See the dlt CLAUDE.md note.
    """

    @dlt.resource(name=table.name, write_disposition="replace", parallelized=True)
    def _table_rows() -> Iterator:
        if signature is not None:
            dlt.current.resource_state()["signature"] = signature

        # One engine per resource: parallelized resources run in separate worker
        # threads, so each needs its own connection pool over the shared tunnel.
        # arraysize: the driver default of 100 rows/fetch makes the extract
        # latency-bound over the WAN tunnel (~2.5k rows/s at ~40ms RTT).
        # Runtime-tunable via the `dlt_arraysize` run tag (diagnostic sweep).
        engine = sa.create_engine(connection_url, arraysize=arraysize)
        try:
            yield from table_rows(
                engine=engine,
                table=table.name,
                metadata=sa.MetaData(schema=ORACLE_SCHEMA),
                chunk_size=50000,
                backend="pyarrow",
                incremental=None,
                table_adapter_callback=remove_nullability_adapter,
                reflection_level="full_with_precision",
                backend_kwargs={},
                type_adapter_callback=oracle_number_adapter,
                included_columns=None,
                excluded_columns=None,
                query_adapter_callback=None,
                resolve_foreign_keys=False,
            )
        finally:
            engine.dispose()

    return _table_rows


@dlt.source(name=_SOURCE_NAME)
def _powerschool_source(
    selected: list[PowerSchoolTable],
    signatures: dict[str, dict],
    connection_url: str,
    arraysize: int,
):
    """dlt source narrowed to `selected`, wiring each table's probed signature."""
    for table in selected:
        yield _build_resource(
            table, signatures.get(table.name), connection_url, arraysize
        )


def build_powerschool_dlt_assets(
    code_location: str,
    tables: list[PowerSchoolTable],
    op_tags: dict[str, object] | None = None,
    max_extract_workers: int | None = None,
):
    """Build ONE two-mode @dlt_assets over all PowerSchool tables.

    The selection decision belongs to the caller: the intraday sensor probes,
    gates, and passes per-table signatures via run config (`probe`); the
    nightly schedule and manual launches pass no config and get an
    unconditional full refresh. In both modes the op opens the SSH tunnel and
    runs the pipeline over a source narrowed to the run's asset selection — a
    full `replace` load per table — persisting each table's signature to dlt
    resource_state WITH the load (dlt commits state only from extracted
    resources, so failures self-heal: the old baseline survives and the table
    re-selects next tick). See
    docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md.

    `max_extract_workers` caps concurrent dlt extract workers to avoid
    saturating the single SSH tunnel (see DPY-4011); None leaves dlt's
    default (5). A per-run `dlt_extract_workers` tag overrides this param for
    a manual concurrency sweep.
    """
    dlt_pipeline = build_powerschool_dlt_pipeline(code_location)

    translator = PowerSchoolDagsterDltTranslator(code_location)
    tables_by_key = {_asset_key(code_location, t.name): t for t in tables}

    @dlt_assets(
        # Full source only defines the asset specs; the op runs a narrowed one.
        dlt_source=_powerschool_source(tables, {}, "", 10_000),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__powerschool",
        dagster_dlt_translator=translator,
        group_name="powerschool",
        pool=f"dlt_powerschool_{code_location}",
        op_tags=op_tags,
    )
    def _assets(
        context: AssetExecutionContext,
        config: PowerSchoolDltConfig,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> Iterator:
        workers = _resolve_extract_workers(
            context.run.tags.get("dlt_extract_workers"), max_extract_workers
        )
        if workers is not None:
            # Set via dlt's config accessor (an in-memory provider that
            # pipeline.extract() resolves `workers=ConfigValue` from) rather than
            # os.environ — keeps the override inside dlt's config channel instead
            # of mutating the process environment.
            dlt.config["extract.workers"] = workers
            context.log.info(f"dlt extract workers capped at {workers}")

        # Diagnostic knob: Oracle cursor fetch size (rows/round-trip).
        arraysize = int(context.run.tags.get("dlt_arraysize") or 10_000)
        context.log.info(f"dlt oracle arraysize {arraysize}")

        selected = [
            tables_by_key[key]
            for key in context.selected_asset_keys
            if key in tables_by_key
        ]

        with ssh_powerschool.open_ssh_tunnel():
            connection_url = db_powerschool.connection_url()

            if config.probe is not None:
                # Intraday sensor mode: the sensor probed and gated already —
                # persist its signatures with the load, no re-probe.
                signatures: dict[str, dict] = {
                    name: {"count": sig.count, "max_cursor": sig.max_cursor}
                    for name, sig in config.probe.items()
                }
                context.log.info(
                    f"powerschool sensor-selected load: {sorted(signatures)}"
                )
            else:
                # Full-refresh mode (nightly schedule / manual launch): load the
                # whole selection unconditionally. Probe FIRST so fresh baseline
                # signatures persist WITH the load — dlt commits state only from
                # extracted resources, so a post-load write would not round-trip.
                engine = sa.create_engine(connection_url)
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
                context.log.info(f"powerschool full-refresh load: {sorted(signatures)}")

            # Stream dlt's periodic extract/normalize/load progress into the
            # Dagster event log. The factory-built collector defaults to
            # logger="stdout" (step-pod compute logs only); context.log is a
            # DagsterLogManager (a logging.Logger), so pointing the collector at
            # it surfaces progress as structured run events every log_period s.
            dlt_pipeline.collector = LogCollector(
                logger=context.log, log_period=30.0, dump_system_stats=False
            )

            try:
                # fetch_row_count() attaches an authoritative per-table row_count
                # to each materialization's metadata (surfaced in the asset
                # catalog) alongside dagster-dlt's default load metadata.
                yield from dlt.run(
                    context=context,
                    dlt_source=_powerschool_source(
                        selected, signatures, connection_url, arraysize
                    ),
                    dlt_pipeline=dlt_pipeline,
                    dagster_dlt_translator=translator,
                    write_disposition="replace",
                ).fetch_row_count()
            except Exception:
                # Surface dlt's per-table extracted row counts in the run log so a
                # load failure is legible without walking the exception chain.
                trace = dlt_pipeline.last_trace
                if trace is not None and trace.last_normalize_info is not None:
                    context.log.info(
                        "dlt normalize row counts before failure: "
                        f"{trace.last_normalize_info.row_counts}"
                    )
                raise

    return _assets


def _stored_signatures(dlt_pipeline, source_name: str) -> dict[str, dict]:
    """Read last-run per-resource signatures from dlt pipeline state."""
    resources = (
        dlt_pipeline.state.get("sources", {}).get(source_name, {}).get("resources", {})
    )
    return {
        name: res_state["signature"]
        for name, res_state in resources.items()
        if isinstance(res_state, dict) and "signature" in res_state
    }
