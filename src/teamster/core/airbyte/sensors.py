import json
from urllib.parse import urlencode

import pendulum
from dagster import SensorEvaluationContext
from dagster_airbyte import AirbyteCloudResource, AirbyteOutput


def _sensor(context: SensorEvaluationContext, airbyte: AirbyteCloudResource):
    now = pendulum.now()
    cursor = json.loads(context.cursor or "{}")

    connections = airbyte.make_request(endpoint="/connections", method="GET")["data"]

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

        for job in successful_jobs:
            job_details = airbyte.get_job_status(
                connection_id=connection_id, job_id=job["jobId"]
            )

            (AirbyteOutput(job_details=job_details, connection_details=connection), [])

        if successful_jobs:
            cursor[connection_id] = now.timestamp()
