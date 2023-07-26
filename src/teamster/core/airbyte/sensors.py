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


def build_airbyte_job_status_sensor(asset_defs):
    @sensor(
        name="airbyte_job_status_sensor",
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(context: SensorEvaluationContext, airbyte: AirbyteCloudResource):
        now_timestamp = pendulum.now().timestamp()

        cursor = json.loads(context.cursor or "{}")

        connections = airbyte.make_request(endpoint="/connections", method="GET")[
            "data"
        ]

        asset_selection = []
        for connection in connections:
            connection_id = connection["connectionId"]

            last_updated = pendulum.from_timestamp(
                timestamp=cursor.get(connection_id, 0)
            )

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
                    asset_selection.append(
                        AssetKey(
                            [
                                namespace_parts[0],
                                "_".join(namespace_parts[1:]),
                                stream["name"],
                            ]
                        )
                    )

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

    return _sensor
