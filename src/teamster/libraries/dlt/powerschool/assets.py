import os
from collections.abc import Iterator
from urllib.parse import quote

import dlt
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

LOAD_STRATEGIES = {"full_refresh": "replace"}


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
    table_name: str,
    load_strategy: str = "full_refresh",
    op_tags: dict[str, object] | None = None,
):
    if load_strategy not in LOAD_STRATEGIES:
        raise ValueError(
            f"load_strategy {load_strategy!r} not supported; "
            f"expected one of {sorted(LOAD_STRATEGIES)}"
        )

    write_disposition = LOAD_STRATEGIES[load_strategy]

    if op_tags is None:
        op_tags = {}

    # dagster-dlt's @dlt_assets requires a DltSource (it reads
    # .selected_resources); sql_table() alone returns a bare DltResource. Wrap
    # it in a @dlt.source generator — the same shape dlt's own sql_database()
    # and libraries/dlt/illuminate/assets.py use.
    @dlt.source(name=f"powerschool_{table_name}")
    def dlt_source():
        # placeholder credentials at import time; real values resolve in the
        # run pod because sql_table defers connection until extraction
        yield sql_table(
            credentials=_oracle_connection_url(),
            schema=ORACLE_SCHEMA,
            table=table_name,
            backend="pyarrow",
            reflection_level="full_with_precision",
            defer_table_reflect=True,
            table_adapter_callback=remove_nullability_adapter,
            type_adapter_callback=oracle_number_adapter,
        )

    dlt_pipeline = dlt.pipeline(
        pipeline_name=f"powerschool_{table_name}",
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_powerschool",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source(),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__powerschool__{table_name}",
        dagster_dlt_translator=PowerSchoolDagsterDltTranslator(code_location),
        group_name="powerschool",
        pool=f"dlt_powerschool_{code_location}",
        op_tags=op_tags,
    )
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
    ) -> Iterator:
        with ssh_powerschool.open_ssh_tunnel_paramiko():
            yield from dlt.run(context=context, write_disposition=write_disposition)

    return _assets
