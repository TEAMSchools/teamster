import json

from dagster import build_sensor_context, instance_for_test

from teamster.kipptaf.alchemer.sensors import (
    alchemer_survey_metadata_asset_sensor,
    alchemer_survey_response_asset_sensor,
)
from teamster.kipptaf.resources import ALCHEMER_RESOURCE


def test_alchemer_survey_metadata_asset_sensor():
    cursor = {}

    with instance_for_test() as instance:
        sensor_result = alchemer_survey_metadata_asset_sensor(
            context=build_sensor_context(
                cursor=json.dumps(obj=cursor),
                sensor_name=alchemer_survey_metadata_asset_sensor.name,
                instance=instance,
            ),
            alchemer=ALCHEMER_RESOURCE,
        )

    assert len(sensor_result.run_requests) > 0  # type: ignore


def test_alchemer_survey_response_asset_sensor():
    cursor = {}

    with instance_for_test() as instance:
        sensor_result = alchemer_survey_response_asset_sensor(
            context=build_sensor_context(
                cursor=json.dumps(obj=cursor),
                sensor_name=alchemer_survey_response_asset_sensor.name,
                instance=instance,
            ),
            alchemer=ALCHEMER_RESOURCE,
        )

    assert len(sensor_result.run_requests) > 0  # type: ignore
