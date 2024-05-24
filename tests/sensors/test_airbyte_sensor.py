import json

from dagster import build_sensor_context

from teamster.kipptaf.airbyte.sensors import airbyte_job_status_sensor
from teamster.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE


def test_airbyte_job_status_sensor():
    cursor = {}

    context = build_sensor_context(
        cursor=json.dumps(obj=cursor), sensor_name=airbyte_job_status_sensor.name
    )

    sensor_result = airbyte_job_status_sensor(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    asset_events = sensor_result.asset_events

    context.log.info(msg=asset_events)
    assert len(asset_events) > 0
