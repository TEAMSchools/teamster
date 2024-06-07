import json

from dagster import (
    RunRequest,
    SensorResult,
    _check,
    build_sensor_context,
    instance_for_test,
)

from teamster.code_locations.kipptaf.alchemer.sensors import (
    alchemer_survey_metadata_asset_sensor,
    alchemer_survey_response_asset_sensor,
)
from teamster.code_locations.kipptaf.resources import ALCHEMER_RESOURCE


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

    assert isinstance(sensor_result, SensorResult)
    run_requests = _check.inst(sensor_result.run_requests, list[RunRequest])

    assert len(run_requests) > 0


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

    assert isinstance(sensor_result, SensorResult)
    run_requests = _check.inst(sensor_result.run_requests, list[RunRequest])

    assert len(run_requests) > 0
