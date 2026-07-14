"""dlt side of the PowerSchool ODBC spike (#4398). Throwaway — never merge.

Loads three PowerSchool tables from Oracle (via the existing sshpass tunnel)
into BigQuery dataset zz_spike_powerschool_dlt using dlt's sql_table source
with the oracledb thin dialect and pyarrow backend. Incremental on
whenmodified with merge write disposition; the first run of an empty dataset
is effectively a full load.
"""

import os
from collections.abc import Iterator
from urllib.parse import quote

import dlt
from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import sql_table

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.ssh.resources import SSHResource

# table name -> primary key column (PowerSchool dcid is the stable unique id)
SPIKE_TABLES: dict[str, str] = {
    "students": "dcid",
    "storedgrades": "dcid",
    "assignmentscore": "dcid",
}

CURSOR_COLUMN = "whenmodified"


def _oracle_connection_url() -> str:
    """Build the SQLAlchemy URL at call time (env vars exist only in pods).

    The sshpass tunnel forwards localhost:1521 -> PS_SSH_REMOTE_BIND_HOST:1521,
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


class SpikeDltTranslator(DagsterDltTranslator):
    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        return asset_spec.replace_attributes(
            key=AssetKey(
                [
                    CODE_LOCATION,
                    "powerschool",
                    "spike",
                    "dlt",
                    data.resource.name,
                ]
            ),
            deps=[],
        )


def build_dlt_spike_asset(table_name: str, primary_key: str):
    # dagster-dlt's @dlt_assets requires a DltSource (it reads
    # .selected_resources); sql_table() alone returns a bare DltResource. Wrap
    # it in a @dlt.source generator — the same shape dlt's own sql_database()
    # and this repo's libraries/dlt/illuminate/assets.py use.
    @dlt.source(name=f"powerschool_spike_{table_name}")
    def dlt_source():
        # placeholder credentials at import time; real values resolve in the
        # run pod because sql_table defers connection until extraction
        resource = sql_table(
            credentials=_oracle_connection_url(),
            table=table_name,
            backend="pyarrow",
            reflection_level="full_with_precision",
            defer_table_reflect=True,
            incremental=dlt.sources.incremental(CURSOR_COLUMN),
        )
        resource.apply_hints(primary_key=primary_key)
        yield resource

    dlt_pipeline = dlt.pipeline(
        pipeline_name=f"powerschool_spike_{table_name}",
        destination=bigquery(),
        dataset_name="zz_spike_powerschool_dlt",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source(),
        dlt_pipeline=dlt_pipeline,
        name=f"{CODE_LOCATION}__powerschool__spike__dlt__{table_name}",
        dagster_dlt_translator=SpikeDltTranslator(),
        group_name="powerschool_odbc_spike",
    )
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
    ) -> Iterator:
        ssh_tunnel = ssh_powerschool.open_ssh_tunnel()

        try:
            yield from dlt.run(context=context, write_disposition="merge")
        finally:
            ssh_tunnel.kill()

    return _assets


DLT_SPIKE_ASSETS = [
    build_dlt_spike_asset(table_name=t, primary_key=pk)
    for t, pk in SPIKE_TABLES.items()
]
