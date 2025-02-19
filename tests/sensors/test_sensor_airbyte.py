import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.airbyte.sensors import airbyte_job_status_sensor
from teamster.code_locations.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE


def test_airbyte_job_status_sensor():
    cursor = {
        "e4856fb7-1f97-4bcd-bc4e-e616c5ae4e52": 1739500000.000000,
        "ee23720c-c82f-45be-ab40-f72dcf8ac3cd": 1739500000.000000,
    }

    context = build_sensor_context(
        cursor=json.dumps(obj=cursor), sensor_name=airbyte_job_status_sensor.name
    )

    sensor_result = airbyte_job_status_sensor(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    assert isinstance(sensor_result, SensorResult)

    context.log.info(msg=sensor_result.asset_events)
    assert len(sensor_result.asset_events) > 0

    context.log.info(msg=sensor_result.cursor)
