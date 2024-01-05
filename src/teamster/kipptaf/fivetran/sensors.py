import json
import re

import pendulum
from dagster import AssetKey, RunRequest, SensorEvaluationContext, SensorResult, sensor
from dagster_fivetran import FivetranResource
from dagster_gcp import BigQueryResource

from .. import CODE_LOCATION
from . import assets

CONNECTORS = {}
ASSET_KEYS = [key for a in assets for key in a.keys]

for asset in assets:
    connector_id = re.match(
        pattern=r"fivetran_sync_(\w+)",
        string=asset.op.name,
    ).group(1)

    CONNECTORS[connector_id] = set([".".join(key.path[1:-1]) for key in asset.keys])


def render_fivetran_audit_query(dataset, timestamp):
    # trunk-ignore(bandit/B608)
    return f"""
        select table_id from {dataset}.__TABLES__
        where last_modified_time >= {timestamp}
    """


@sensor(
    name=f"{CODE_LOCATION}_fivetran_sync_status_sensor",
    minimum_interval_seconds=(60 * 5),
    asset_selection=assets,
)
def fivetran_sync_status_sensor(
    context: SensorEvaluationContext,
    fivetran: FivetranResource,
    db_bigquery: BigQueryResource,
) -> SensorResult:
    cursor: dict = json.loads(s=(context.cursor or "{}"))

    with db_bigquery.get_client() as bq:
        bq = bq

    asset_keys = []
    for connector_id, connector_schemas in CONNECTORS.items():
        # check if fivetran sync has completed
        (
            curr_last_sync_completion,
            curr_last_sync_succeeded,
            curr_sync_state,
        ) = fivetran.get_connector_sync_status(connector_id)

        context.log.info(
            msg=(
                f"Polled '{connector_id}'. "
                f"Status: [{curr_sync_state}] @ {curr_last_sync_completion}"
            )
        )

        curr_last_sync_completion_timestamp = curr_last_sync_completion.timestamp()
        last_update_timestamp = cursor.get(connector_id, 0)

        if (
            curr_last_sync_succeeded
            and curr_last_sync_completion_timestamp > last_update_timestamp
        ):
            for schema in connector_schemas:
                # get BQ table metadata
                query = render_fivetran_audit_query(
                    dataset=schema.replace(".", "_"),
                    timestamp=(last_update_timestamp * 1000),
                )

                context.log.info(query)
                query_job = bq.query(query=query)

                for row in query_job.result():
                    context.log.info(row.table_id)

                    asset_key = AssetKey(
                        [CODE_LOCATION, *schema.split("."), row.table_id]
                    )

                    if asset_key in ASSET_KEYS:
                        asset_keys.append(asset_key)

            cursor[connector_id] = curr_last_sync_completion_timestamp

    if asset_keys:
        run_requests = [
            RunRequest(
                run_key=f"{context.sensor_name}_{pendulum.now().timestamp()}",
                asset_selection=asset_keys,
            )
        ]
    else:
        run_requests = []

    return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))


_all = [
    fivetran_sync_status_sensor,
]
