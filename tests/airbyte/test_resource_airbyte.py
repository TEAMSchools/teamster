import pendulum
from dagster import EnvVar, build_resources
from dagster_airbyte import AirbyteCloudResource


def test_resource():
    with build_resources(
        resources={"airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY"))}
    ) as resources:
        airbyte: AirbyteCloudResource = resources.airbyte

        last_checked = pendulum.from_timestamp(timestamp=0)

        jobs = airbyte.make_request(
            endpoint="/jobs",
            data={"updatedAtStart": last_checked.format("YYYY-MM-DDTHH:mm:ssZ")},
            method="GET",
        )

        print(jobs)
