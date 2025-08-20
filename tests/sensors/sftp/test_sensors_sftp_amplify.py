from dagster import SensorResult, build_sensor_context


def _test_sensor(sensor, ssh_amplify):
    context = build_sensor_context(sensor_name=sensor.name)

    result: SensorResult = sensor(context=context, ssh_amplify=ssh_amplify)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


def test_amplify_sftp_sensor_kipptaf():
    from teamster.code_locations.kipptaf.amplify.mclass.sftp.sensors import (
        amplify_mclass_sftp_sensor,
    )
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_AMPLIFY

    _test_sensor(sensor=amplify_mclass_sftp_sensor, ssh_amplify=SSH_RESOURCE_AMPLIFY)
