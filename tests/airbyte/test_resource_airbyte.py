from urllib.parse import urlencode

import pendulum
from dagster import AssetKey, EnvVar, build_resources
from dagster_airbyte import AirbyteCloudResource


def test_resource():
    with build_resources(
        resources={"airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY"))}
    ) as resources:
        airbyte: AirbyteCloudResource = resources.airbyte

    connections = airbyte.make_request(endpoint="/connections", method="GET")["data"]

    # airbyte_outputs: list[AirbyteOutput] = []
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

        successful_jobs = airbyte.make_request(
            endpoint=f"/jobs?{params}", method="GET"
        ).get("data", [])

        if successful_jobs:
            namespace_parts = connection["namespaceFormat"].split("_")
            for stream in connection["configurations"]["streams"]:
                asset_key = AssetKey(
                    [namespace_parts[0], "_".join(namespace_parts[1:]), stream["name"]]
                )
                print(asset_key)
