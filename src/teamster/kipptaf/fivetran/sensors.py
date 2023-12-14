import json
import re

import pendulum
from dagster import (
    AssetKey,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_fivetran import FivetranResource
from dagster_gcp import BigQueryResource

from .. import CODE_LOCATION
from . import assets

SENSOR_ASSET_SELECTION = AssetSelection.assets(*assets)

CONNECTORS = {}
for asset in assets:
    connector_id = re.match(pattern=r"fivetran_sync_(\w+)", string=asset.op.name).group(
        1
    )

    CONNECTORS[connector_id] = set([".".join(key.path[1:-1]) for key in asset.keys])


def render_fivetran_audit_query(connector_id, timestamp):
    return f"""
        select distinct
            json_extract_scalar(message_data, '$.table') as table_name,
        from fivetran_log.log
        where
            connector_id = '{connector_id}'
            and message_event = 'records_modified'
            and _fivetran_synced >= '{timestamp}'
    """


@sensor(
    name=f"{CODE_LOCATION}_fivetran_sync_status_sensor",
    minimum_interval_seconds=(60 * 1),
    asset_selection=SENSOR_ASSET_SELECTION,
)
def fivetran_sync_status_sensor(
    context: SensorEvaluationContext,
    fivetran: FivetranResource,
    db_bigquery: BigQueryResource,
):
    cursor: dict = json.loads(s=(context.cursor or "{}"))

    with db_bigquery.get_client() as bq:
        bq = bq

    asset_keys = []
    for connector_id, connector_schemas in CONNECTORS.items():
        # check if fivetran sync has completed
        last_update = pendulum.from_timestamp(cursor.get(connector_id, 0))

        (
            curr_last_sync_completion,
            curr_last_sync_succeeded,
            curr_sync_state,
        ) = fivetran.get_connector_sync_status(connector_id)

        context.log.info(
            (
                f"Polled '{connector_id}'. "
                f"Status: [{curr_sync_state}] @ {curr_last_sync_completion}"
            )
        )

        curr_last_sync_completion_timestamp = curr_last_sync_completion.timestamp()

        if (
            curr_last_sync_succeeded
            and curr_last_sync_completion_timestamp > last_update.timestamp()
        ):
            for schema in connector_schemas:
                # get fivetran_audit table
                query = render_fivetran_audit_query(
                    connector_id=connector_id, timestamp=last_update.to_iso8601_string()
                )
                context.log.info(query)

                query_job = bq.query(query=query)

                for row in query_job.result():
                    context.log.info(row)

                    asset_key = AssetKey(
                        [CODE_LOCATION, *schema.split("."), row.table_name]
                    )

                    if asset_key in SENSOR_ASSET_SELECTION._keys:
                        asset_keys.append(asset_key)

            cursor[connector_id] = curr_last_sync_completion_timestamp

    if asset_keys:
        return SensorResult(
            run_requests=[
                RunRequest(
                    run_key=f"{context.sensor_name}_{pendulum.now().timestamp()}",
                    asset_selection=asset_keys,
                )
            ],
            cursor=json.dumps(obj=cursor),
        )


_all = [
    fivetran_sync_status_sensor,
]
