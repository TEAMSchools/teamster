from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from dagster import AssetKey, EnvVar, build_resources
from dagster_airbyte import AirbyteCloudWorkspace
from dagster_shared import check


def test_resource():
    with build_resources(
        resources={
            "airbyte": AirbyteCloudWorkspace(
                workspace_id=EnvVar(), client_id=EnvVar(), client_secret=EnvVar()
            )
        }
    ) as resources:
        airbyte: AirbyteCloudWorkspace = resources.airbyte

    connections_response = check.not_none(
        airbyte.make_request(endpoint="/connections", method="GET")
    )

    connections = check.inst(connections_response["data"], dict)

    # airbyte_outputs: list[AirbyteOutput] = []
    for connection in connections:
        connection_id = connection["connectionId"]

        last_updated = datetime.now(timezone.utc) - timedelta(days=1)

        params = urlencode(
            query={
                "connectionId": connection_id,
                "updatedAtStart": last_updated.isoformat(),
                "status": "succeeded",
            }
        )

        succeeded_jobs_response = check.not_none(
            airbyte.make_request(endpoint=f"/jobs?{params}", method="GET")
        )

        if succeeded_jobs_response.get("data") is not None:
            namespace_parts = connection["namespaceFormat"].split("_")
            for stream in connection["configurations"]["streams"]:
                asset_key = AssetKey(
                    [namespace_parts[0], "_".join(namespace_parts[1:]), stream["name"]]
                )
                print(asset_key)
