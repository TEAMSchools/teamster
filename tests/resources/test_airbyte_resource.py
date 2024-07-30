from urllib.parse import urlencode

import pendulum
from dagster import AssetKey, EnvVar, _check, build_resources
from dagster_airbyte import AirbyteCloudResource


def test_resource():
    with build_resources(
        resources={"airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY"))}
    ) as resources:
        airbyte: AirbyteCloudResource = resources.airbyte

    connections_response = _check.not_none(
        airbyte.make_request(endpoint="/connections", method="GET")
    )

    connections = _check.inst(connections_response["data"], dict)

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

        succeeded_jobs_response = _check.not_none(
            airbyte.make_request(endpoint=f"/jobs?{params}", method="GET")
        )

        if succeeded_jobs_response.get("data") is not None:
            namespace_parts = connection["namespaceFormat"].split("_")
            for stream in connection["configurations"]["streams"]:
                asset_key = AssetKey(
                    [namespace_parts[0], "_".join(namespace_parts[1:]), stream["name"]]
                )
                print(asset_key)
