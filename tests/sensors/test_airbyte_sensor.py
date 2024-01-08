import json

from dagster import build_sensor_context

from teamster.kipptaf.airbyte.sensors import airbyte_job_status_sensor
from teamster.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE


def test_airbyte_job_status_sensor():
    CURSOR = {}

    sensor_result = airbyte_job_status_sensor(
        context=build_sensor_context(
            cursor=json.dumps(obj=CURSOR), sensor_name=airbyte_job_status_sensor.name
        ),
        airbyte=AIRBYTE_CLOUD_RESOURCE,
    )

    assert len(sensor_result.run_requests) > 0  # type: ignore
