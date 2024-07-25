from dagster import SensorResult, build_sensor_context

from teamster.libraries.core.resources import SSH_COUCHDROP


def _test_sensor(sftp_sensor):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, ssh_couchdrop=SSH_COUCHDROP)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)

    print(result.cursor)


def test_couchdrop_sftp_sensor_kippcamden():
    from teamster.code_locations.kippcamden.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor)


def test_couchdrop_sftp_sensor_kippmiami():
    from teamster.code_locations.kippmiami.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor)


def test_couchdrop_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor)
