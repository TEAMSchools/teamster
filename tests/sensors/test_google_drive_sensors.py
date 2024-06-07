from dagster import SensorResult, _check, build_sensor_context, instance_for_test

from teamster.code_locations.kipptaf.google.drive.sensors import (
    google_forms_partition_sensor,
)
from teamster.code_locations.kipptaf.resources import GOOGLE_DRIVE_RESOURCE


def test_alchemer_survey_metadata_asset_sensor():
    with instance_for_test() as instance:
        context = build_sensor_context(
            sensor_name=google_forms_partition_sensor.name, instance=instance
        )

        sensor_result = google_forms_partition_sensor(
            context=context, google_drive=GOOGLE_DRIVE_RESOURCE
        )

        assert isinstance(sensor_result, SensorResult)
        context.log.info(sensor_result.dynamic_partitions_requests)

    dynamic_partitions_requests = _check.not_none(
        sensor_result.dynamic_partitions_requests
    )

    assert len(dynamic_partitions_requests) > 0
