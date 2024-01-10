import json
from urllib.parse import urlencode

import pendulum
from dagster import (
    AssetKey,
    AssetMaterialization,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_airbyte import AirbyteCloudResource

from .. import CODE_LOCATION
from . import assets

ASSET_KEYS = [key for a in assets for key in a.keys]


@sensor(
    name=f"{CODE_LOCATION}_airbyte_job_status_sensor",
    minimum_interval_seconds=(60 * 5),
    asset_selection=assets,
)
def airbyte_job_status_sensor(
    context: SensorEvaluationContext, airbyte: AirbyteCloudResource
) -> SensorResult:
    now_timestamp = pendulum.now().timestamp()
    asset_events = []

    cursor = json.loads(context.cursor or "{}")

    connections = airbyte.make_request(endpoint="/connections", method="GET")

    for connection in connections["data"]:  # type: ignore
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

                if asset_key in ASSET_KEYS:
                    context.log.info(asset_key)
                    asset_events.append(AssetMaterialization(asset_key=asset_key))

    return SensorResult(asset_events=asset_events, cursor=json.dumps(obj=cursor))


_all = [
    airbyte_job_status_sensor,
]
