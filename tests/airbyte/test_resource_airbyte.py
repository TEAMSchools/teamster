from urllib.parse import urlencode

import pendulum
from dagster import EnvVar, build_resources
from dagster_airbyte import AirbyteCloudResource, AirbyteOutput


def test_resource():
    with build_resources(
        resources={"airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY"))}
    ) as resources:
        airbyte: AirbyteCloudResource = resources.airbyte

    connections = airbyte.make_request(endpoint="/connections", method="GET")["data"]

    successful_job_outputs = []
    for connection in connections:
        connection_id = connection["connectionId"]

        last_updated = pendulum.today().subtract(days=1)

        params = urlencode(
            query={
                "connectionId": connection_id,
                "updatedAtStart": last_updated.format("YYYY-MM-DDTHH:mm:ss[Z]"),
                "status": "succeeded",
            }
        )

        jobs = airbyte.make_request(endpoint=f"/jobs?{params}", method="GET").get(
            "data", []
        )

        for job in jobs:
            job_details = airbyte.get_job_status(
                connection_id=connection_id, job_id=job["jobId"]
            )

            successful_job_outputs.append(
                AirbyteOutput(job_details=job_details, connection_details=connection)
            )

    print(successful_job_outputs)
