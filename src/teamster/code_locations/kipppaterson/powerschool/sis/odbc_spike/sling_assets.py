"""Sling side of the PowerSchool ODBC spike (#4398). Throwaway — never merge.

Replicates the same three tables through Sling's native SSH tunnel into
BigQuery dataset zz_spike_powerschool_sling. mode: incremental with a per-table
update_key (see SPIKE_TABLES) — on an empty target this performs the initial
full load; subsequent runs are incremental from max(update_key) in the target.
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
    ORACLE_SCHEMA,
    SPIKE_TABLES,
)


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
            # PS_DB_DATABASE is a service name (the prod ODBC resource passes it
            # as service_name, not SID); Sling accepts service_name as a
            # distinct property. Using sid= here would fail with ORA-12514.
            service_name=os.getenv("PS_DB_DATABASE", ""),
            ssh_tunnel=_ssh_tunnel_url(),
        ),
        SlingConnectionResource(
            name="BIGQUERY_SPIKE",
            type="bigquery",
            project=GCS_PROJECT_NAME,
            dataset="zz_spike_powerschool_sling",
            # No gc_bucket on purpose. Sling's GCS-staging fast path fails on our
            # keyless GKE Workload Identity environment with "Could not connect
            # to GS Storage: dialing: multiple credential options provided": its
            # fs_google.go ADC branch passes option.WithCredentials(creds) while
            # the bundled google-cloud-go storage client also auto-detects ADC,
            # which google.golang.org/api >= v0.258.0 rejects. The WithHTTPClient
            # workaround exists only on the explicit-key branch (both 1.5.20 and
            # main still use the single-option ADC path), so no version bump
            # helps. Omitting the bucket routes the load through the BigQuery
            # client directly (which authenticates fine), matching dlt's keyless
            # load path — slower than GCS bulk staging, fine for spike volumes.
            location="US",
        ),
    ]
)

REPLICATION_CONFIG = {
    "source": "PS_ORACLE",
    "target": "BIGQUERY_SPIKE",
    "defaults": {
        "mode": "incremental",
        "object": "zz_spike_powerschool_sling.{stream_table}",
        # format=parquet: Sling's default keyless BigQuery load stages through
        # CSV, which chokes on PowerSchool free-text columns (embedded newlines /
        # quotes / delimiters in course names + comments) — storedgrades failed
        # "CSV processing encountered too many errors ... max bad: 0". Parquet is
        # typed/binary and immune to this (Sling's own error log recommends it).
        # dlt sidesteps it entirely via its native pyarrow backend.
        "target_options": {"column_casing": "snake", "format": "parquet"},
    },
    "streams": {
        f"{ORACLE_SCHEMA}.{table}": {
            "primary_key": [cfg["primary_key"]],
            "update_key": cfg["cursor"],
        }
        for table, cfg in SPIKE_TABLES.items()
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
