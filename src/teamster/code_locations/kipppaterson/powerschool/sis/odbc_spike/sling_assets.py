"""Sling side of the PowerSchool ODBC spike (#4398). Throwaway — never merge.

Replicates the same three tables through Sling's native SSH tunnel into
BigQuery dataset zz_spike_powerschool_sling. mode: incremental with
update_key whenmodified — on an empty target this performs the initial full
load; subsequent runs are incremental from max(whenmodified) in the target.
"""

import os
from collections.abc import Iterator
from urllib.parse import quote

from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_sling import (
    DagsterSlingTranslator,
    SlingConnectionResource,
    SlingResource,
    sling_assets,
)

from teamster import GCS_PROJECT_NAME
from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
    CURSOR_COLUMN,
    SPIKE_TABLES,
)

# Oracle table qualification: the ODBC user's default schema resolves
# unqualified names today; Sling streams are qualified explicitly. If runtime
# errors show "table not found", change to the owner schema discovered in
# Task 4 (expected: ps).
ORACLE_SCHEMA = "ps"


def _ssh_tunnel_url() -> str:
    """ssh://user:password@host:port — password auth, no key file."""
    user = os.getenv("PS_SSH_USERNAME", "")
    password = quote(os.getenv("PS_SSH_PASSWORD", ""), safe="")
    host = os.getenv("PS_SSH_HOST", "")
    port = os.getenv("PS_SSH_PORT", "22")

    return f"ssh://{user}:{password}@{host}:{port}"


SLING_SPIKE_RESOURCE = SlingResource(
    connections=[
        SlingConnectionResource(
            name="PS_ORACLE",
            type="oracle",
            host=os.getenv("PS_SSH_REMOTE_BIND_HOST", ""),
            port=1521,
            user=os.getenv("PS_DB_USERNAME", ""),
            password=os.getenv("PS_DB_PASSWORD", ""),
            sid=os.getenv("PS_DB_DATABASE", ""),
            ssh_tunnel=_ssh_tunnel_url(),
        ),
        SlingConnectionResource(
            name="BIGQUERY_SPIKE",
            type="bigquery",
            project=GCS_PROJECT_NAME,
            dataset="zz_spike_powerschool_sling",
            gc_bucket="teamster-test",
            location="US",
        ),
    ]
)

REPLICATION_CONFIG = {
    "source": "PS_ORACLE",
    "target": "BIGQUERY_SPIKE",
    "defaults": {
        "mode": "incremental",
        "update_key": CURSOR_COLUMN,
        "object": "zz_spike_powerschool_sling.{stream_table}",
        "target_options": {"column_casing": "snake"},
    },
    "streams": {
        f"{ORACLE_SCHEMA}.{table}": {"primary_key": [pk]}
        for table, pk in SPIKE_TABLES.items()
    },
}


class SpikeSlingTranslator(DagsterSlingTranslator):
    def get_asset_spec(self, stream_definition) -> AssetSpec:
        asset_spec = super().get_asset_spec(stream_definition)

        # stream name is "<schema>.<table>" — key on the bare table name
        table_name = stream_definition["name"].split(".")[-1]

        return asset_spec.replace_attributes(
            key=AssetKey([CODE_LOCATION, "powerschool", "spike", "sling", table_name]),
            deps=[],
        )


@sling_assets(
    replication_config=REPLICATION_CONFIG,
    dagster_sling_translator=SpikeSlingTranslator(),
    name=f"{CODE_LOCATION}__powerschool__spike__sling",
)
def sling_spike_assets(
    context: AssetExecutionContext, sling: SlingResource
) -> Iterator:
    yield from sling.replicate(context=context)

    for row in sling.stream_raw_logs():
        context.log.info(row)


SLING_SPIKE_ASSETS = [sling_spike_assets]
