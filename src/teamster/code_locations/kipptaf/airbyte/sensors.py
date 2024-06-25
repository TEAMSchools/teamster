import json
from urllib.parse import urlencode

import pendulum
from dagster import (
    AssetKey,
    AssetMaterialization,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)
from dagster_airbyte import AirbyteCloudResource

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.airbyte import assets

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

    connections = _check.not_none(
        airbyte.make_request(endpoint="/connections", method="GET")
    )

    for connection in _check.inst(connections["data"], list):
        if connection["status"] == "inactive":
            continue

        context.log.info(connection["name"])
        connection_id = connection["connectionId"]

        last_updated = pendulum.from_timestamp(timestamp=cursor.get(connection_id, 0))

        params = urlencode(
            query={
                "connectionId": connection_id,
                "updatedAtStart": last_updated.format("YYYY-MM-DDTHH:mm:ss[Z]"),
                "status": "succeeded",
            }
        )

        jobs_response = _check.not_none(
            airbyte.make_request(endpoint=f"/jobs?{params}", method="GET")
        )

        if jobs_response.get("data"):
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


sensors = [
    airbyte_job_status_sensor,
]
