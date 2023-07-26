import json
from urllib.parse import urlencode

import pendulum
from dagster import RunConfig, RunRequest, SensorEvaluationContext, SensorResult, sensor
from dagster_airbyte import AirbyteCloudResource

from teamster.core.airbyte.jobs import airbyte_materialization_job
from teamster.core.airbyte.ops import AirbyteMaterializationOpConfig


@sensor(job=airbyte_materialization_job)
def airbyte_job_status_sensor(
    context: SensorEvaluationContext, airbyte: AirbyteCloudResource
):
    now = pendulum.now()

    cursor = json.loads(context.cursor or "{}")

    connections = airbyte.make_request(endpoint="/connections", method="GET")["data"]

    airbyte_outputs = []
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

            airbyte_outputs.append(
                {"job_details": job_details, "connection_details": connection}
            )

        if successful_jobs:
            cursor[connection_id] = now.timestamp()

    if airbyte_outputs:
        run_requests = [
            RunRequest(
                run_key=f"{context._sensor_name}_{pendulum.now().timestamp()}",
                run_config=RunConfig(
                    ops={
                        "airbyte_materialization_op": AirbyteMaterializationOpConfig(
                            airbyte_outputs=airbyte_outputs
                        )
                    }
                ),
            )
        ]

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))
