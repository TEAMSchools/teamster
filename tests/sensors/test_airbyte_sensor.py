import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.airbyte.sensors import airbyte_job_status_sensor
from teamster.code_locations.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE


def test_airbyte_job_status_sensor():
    cursor = {}

    context = build_sensor_context(
        cursor=json.dumps(obj=cursor), sensor_name=airbyte_job_status_sensor.name
    )

    sensor_result = airbyte_job_status_sensor(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    assert isinstance(sensor_result, SensorResult)

    context.log.info(msg=sensor_result.asset_events)
    assert len(sensor_result.asset_events) > 0
