import json
from urllib.parse import urlencode

import pendulum
from dagster import (
    AssetKey,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_airbyte import AirbyteCloudResource

from .. import CODE_LOCATION
from . import assets

sensor_asset_selection = AssetSelection.assets(*assets)


@sensor(
    name=f"{CODE_LOCATION}_airbyte_job_status_sensor",
    minimum_interval_seconds=(60 * 1),
    asset_selection=sensor_asset_selection,
)
def airbyte_job_status_sensor(
    context: SensorEvaluationContext, airbyte: AirbyteCloudResource
):
    now_timestamp = pendulum.now().timestamp()

    cursor = json.loads(context.cursor or "{}")

    connections = airbyte.make_request(endpoint="/connections", method="GET")["data"]

    asset_selection = []
    for connection in connections:
        connection_id = connection["connectionId"]

        last_updated = pendulum.from_timestamp(timestamp=cursor.get(connection_id, 0))

        params = urlencode(
            query={
                "connectionId": connection_id,
                "updatedAtStart": last_updated.format("YYYY-MM-DDTHH:mm:ss[Z]"),
                "status": "succeeded",
            }
        )

        successful_jobs = airbyte.make_request(
            endpoint=f"/jobs?{params}", method="GET"
        ).get("data", [])

        if successful_jobs:
            cursor[connection_id] = now_timestamp

            namespace_parts = connection["namespaceFormat"].split("_")

            for stream in connection["configurations"]["streams"]:
                asset_key = AssetKey(
                    [namespace_parts[0], "_".join(namespace_parts[1:]), stream["name"]]
                )

                if asset_key in sensor_asset_selection._keys:
                    asset_selection.append(asset_key)

    if asset_selection:
        return SensorResult(
            run_requests=[
                RunRequest(
                    run_key=f"{context._sensor_name}_{now_timestamp}",
                    asset_selection=asset_selection,
                )
            ],
            cursor=json.dumps(obj=cursor),
        )


__all__ = [
    airbyte_job_status_sensor,
]
