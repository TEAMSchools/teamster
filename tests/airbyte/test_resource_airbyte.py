from urllib.parse import urlencode

import pendulum
from dagster import EnvVar, build_resources
from dagster_airbyte import AirbyteCloudResource, AirbyteOutput

GCS_PROJECT_NAME = "teamster-332318"


def render_fivetran_audit_query(dataset, done):
    return f"""
        select distinct table
        from {dataset}.fivetran_audit
        where done >= '{done}'
    """


def test_resource():
    with build_resources(
        resources={"airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY"))}
    ) as resources:
        airbyte: AirbyteCloudResource = resources.airbyte

    connections = airbyte.make_request(endpoint="/connections", method="GET")["data"]

    # sensor
    airbyte_outputs: list[AirbyteOutput] = []
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

            airbyte_outputs.append(
                AirbyteOutput(job_details=job_details, connection_details=connection)
            )

    # op
    for output in airbyte_outputs:
        namespace_format = output.connection_details["namespaceFormat"]
        asset_key_parts = namespace_format.split("_")

        print(output)
        print([asset_key_parts[0], "_".join(asset_key_parts[1:])])
