import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import quote

import dlt
import sqlalchemy as sa
from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import remove_nullability_adapter
from dlt.sources.sql_database.helpers import table_rows
from sqlalchemy import Float, Numeric
from sqlalchemy.types import TypeEngine

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
    connection, table_name: str, cursor_column: str
) -> dict[str, int | str | None]:
    """Fetch the change signature for a table: total count + max cursor.

    Equality-compared against the stored signature; drift in either value
    (including a cursor regression) triggers a full replace. Values are
    JSON-serializable for dlt resource state.
    """
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

    return {"count": count, "max_cursor": max_cursor_value}


def _compute_changed(
    selected: list[PowerSchoolTable],
    current: dict[str, dict],
    stored: dict[str, dict],
) -> list[PowerSchoolTable]:
    """Select tables to load: no-cursor tables always, cursor tables on drift.

    A table is changed when it has no cursor column (always reloaded when
    selected) or its just-probed signature differs from the stored one
    (drift, or first run when stored has no entry).
    """
    return [
        table
        for table in selected
        if table.cursor_column is None
        or current.get(table.name) != stored.get(table.name)
    ]


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


def _oracle_connection_url() -> str:
    """Build the SQLAlchemy URL at call time (env vars exist only in pods).

    The SSH tunnel forwards localhost:1521 -> PS_SSH_REMOTE_BIND_HOST:1521,
    so the DB host here is the tunnel-local endpoint (PS_DB_HOST, normally
    localhost), matching the existing ODBC resource's connection shape.
    """
    user = os.getenv("PS_DB_USERNAME", "")
    password = quote(os.getenv("PS_DB_PASSWORD", ""), safe="")
    host = os.getenv("PS_DB_HOST", "localhost")
    port = os.getenv("PS_DB_PORT", "1521")
    service_name = os.getenv("PS_DB_DATABASE", "")

    return (
        f"oracle+oracledb://{user}:{password}@{host}:{port}"
        f"/?service_name={service_name}"
    )


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


def _build_resource(table: PowerSchoolTable, signature: dict | None):
    """Build one full-replace, parallel-extracted dlt resource for a table.

    When a signature is provided it is persisted to the resource's dlt state
    with the load package (so the next run can detect drift). No-cursor tables
    are passed signature=None and carry no stored signature.

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
        engine = sa.create_engine(_oracle_connection_url())
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
def _powerschool_source(selected: list[PowerSchoolTable], signatures: dict[str, dict]):
    """dlt source narrowed to `selected`, wiring each table's probed signature."""
    for table in selected:
        yield _build_resource(table, signatures.get(table.name))


def build_powerschool_dlt_assets(
    code_location: str,
    tables: list[PowerSchoolTable],
    op_tags: dict[str, object] | None = None,
):
    """Build ONE probe-gated @dlt_assets over all PowerSchool tables.

    The op opens the SSH tunnel, restores prior per-table signatures from dlt
    resource_state (persisted in the destination), probes each selected table's
    COUNT(*)/MAX(cursor), and runs the pipeline over a source narrowed to only
    the changed tables (`_powerschool_source(changed, current)`) — a full `replace`
    load per changed table. Tables without a cursor_column are always loaded
    when selected.
    Unselected / unchanged tables are never in the run, so their destination
    tables are untouched. Schedules subset the multi-asset per tier. See
    docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md.
    """
    dlt_pipeline = dlt.pipeline(
        pipeline_name=_SOURCE_NAME,
        # No `autodetect_schema=True`: oracle_number_adapter +
        # full_with_precision reflection are the authoritative decimal schema
        # (see oracle_number_adapter docstring).
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_{_SOURCE_NAME}",
        progress=LogCollector(dump_system_stats=False),
    )

    translator = PowerSchoolDagsterDltTranslator(code_location)
    tables_by_key = {_asset_key(code_location, t.name): t for t in tables}

    @dlt_assets(
        # Full source only defines the asset specs; the op runs a narrowed one.
        dlt_source=_powerschool_source(tables, {}),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__powerschool",
        dagster_dlt_translator=translator,
        group_name="powerschool",
        pool=f"dlt_powerschool_{code_location}",
        op_tags=op_tags,
    )
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
    ) -> Iterator:
        selected = [
            tables_by_key[key]
            for key in context.selected_asset_keys
            if key in tables_by_key
        ]

        with ssh_powerschool.open_ssh_tunnel_paramiko():
            # Restore prior signatures from the destination state table. On a
            # truly first run (no dataset) this raises; treat as no prior state.
            try:
                dlt_pipeline.sync_destination()
            except Exception as e:
                context.log.info(
                    f"dlt sync_destination failed ({e}); treating all selected "
                    "as changed"
                )

            stored = _stored_signatures(dlt_pipeline, _SOURCE_NAME)

            # Probe every selected table that has a cursor column (one shared
            # engine over the single tunnel).
            engine = sa.create_engine(_oracle_connection_url())
            try:
                with engine.connect() as connection:
                    current: dict[str, dict] = {
                        table.name: probe_signature(
                            connection, table.name, table.cursor_column
                        )
                        for table in selected
                        if table.cursor_column is not None
                    }
            finally:
                engine.dispose()

            changed = _compute_changed(selected, current, stored)

            context.log.info(
                f"powerschool probe: {len(changed)}/{len(selected)} changed; "
                f"changed={sorted(t.name for t in changed)}"
            )

            if not changed:
                return  # idle tick: nothing to load

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
                    dlt_source=_powerschool_source(changed, current),
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
