import os
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import quote

import dlt
import sqlalchemy as sa
from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import remove_nullability_adapter, sql_table
from sqlalchemy import Float, Numeric
from sqlalchemy.types import TypeEngine

from teamster.libraries.ssh.resources import SSHResource

# PowerSchool tables are owned by the `ps` schema. The ODBC pipeline reaches
# them via unqualified raw SQL (Oracle synonym/default-schema resolution), but
# SQLAlchemy reflection needs the owner schema explicitly or it raises
# NoSuchTableError.
ORACLE_SCHEMA = "ps"


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

    return {
        "count": count,
        "max_cursor": max_cursor.isoformat() if max_cursor is not None else None,
    }


def oracle_number_adapter(col_type: TypeEngine) -> TypeEngine | None:
    """Keep Oracle NUMBER columns off FLOAT64 in BigQuery.

    Decimal Oracle NUMBER columns can reflect as Float (landing as FLOAT64 —
    float drift on GPA/balance columns) or as unbounded Numeric (landing as
    BIGNUMERIC via dlt's decimal128(38, 9+) default). Pin both to
    Numeric(38, 9), which dlt's BigQuery destination maps to NUMERIC.
    """
    if isinstance(col_type, Float):
        return Numeric(precision=38, scale=9)
    if isinstance(col_type, Numeric) and col_type.precision is None:
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
    def __init__(self, code_location: str):
        self.code_location = code_location
        super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=AssetKey([self.code_location, "powerschool", data.resource.name]),
            deps=[],
        )

        return asset_spec.merge_attributes(kinds={"oracle"})


def build_powerschool_dlt_assets(
    code_location: str,
    tables: list[PowerSchoolTable],
    op_tags: dict[str, object] | None = None,
):
    """Build ONE probe-gated @dlt_assets over all PowerSchool tables.

    The op opens the SSH tunnel, restores prior per-table signatures from dlt
    resource_state (persisted in the destination), probes each selected table's
    COUNT(*)/MAX(cursor), and runs the pipeline over only the changed resources
    via source.with_resources(*changed) — a full `replace` load per changed
    table. Tables without a cursor_column are always loaded when selected.
    Unselected / unchanged tables are never in the run, so their destination
    tables are untouched. Schedules subset the multi-asset per tier. See
    docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md.
    """
    source_name = "powerschool"

    def _build_resource(table: PowerSchoolTable, signature: dict | None):
        @dlt.resource(name=table.name, write_disposition="replace")
        def _table_rows() -> Iterator:
            # Persist the just-probed signature with this load package so the
            # next run detects drift. No-cursor tables carry no signature.
            if signature is not None:
                dlt.current.resource_state()["signature"] = signature
            yield from sql_table(
                credentials=_oracle_connection_url(),
                schema=ORACLE_SCHEMA,
                table=table.name,
                backend="pyarrow",
                reflection_level="full_with_precision",
                defer_table_reflect=True,
                table_adapter_callback=remove_nullability_adapter,
                type_adapter_callback=oracle_number_adapter,
            )

        return _table_rows

    def _build_source(selected: list[PowerSchoolTable], signatures: dict[str, dict]):
        @dlt.source(name=source_name)
        def _src():
            for table in selected:
                yield _build_resource(table, signatures.get(table.name))

        return _src()

    dlt_pipeline = dlt.pipeline(
        pipeline_name=source_name,
        # No `autodetect_schema=True`: oracle_number_adapter +
        # full_with_precision reflection are the authoritative decimal schema
        # (see oracle_number_adapter docstring).
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_powerschool",
        progress=LogCollector(dump_system_stats=False),
    )

    translator = PowerSchoolDagsterDltTranslator(code_location)
    tables_by_key = {
        AssetKey([code_location, "powerschool", t.name]): t for t in tables
    }

    @dlt_assets(
        # Full source only defines the asset specs; the op runs a narrowed one.
        dlt_source=_build_source(tables, {}),
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
            except Exception:
                context.log.info("no prior dlt state; all selected are changed")

            stored = _stored_signatures(dlt_pipeline, source_name)

            # Probe every selected table that has a cursor column (one shared
            # engine over the single tunnel).
            current: dict[str, dict] = {}
            engine = sa.create_engine(_oracle_connection_url())
            try:
                with engine.connect() as connection:
                    for table in selected:
                        if table.cursor_column is not None:
                            current[table.name] = probe_signature(
                                connection, table.name, table.cursor_column
                            )
            finally:
                engine.dispose()

            changed = [
                table
                for table in selected
                if table.cursor_column is None
                or current.get(table.name) != stored.get(table.name)
            ]

            context.log.info(
                f"powerschool probe: {len(changed)}/{len(selected)} changed; "
                f"changed={sorted(t.name for t in changed)}"
            )

            if not changed:
                return  # idle tick: nothing to load

            yield from dlt.run(
                context=context,
                dlt_source=_build_source(changed, current),
                dlt_pipeline=dlt_pipeline,
                dagster_dlt_translator=translator,
                write_disposition="replace",
            )

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
