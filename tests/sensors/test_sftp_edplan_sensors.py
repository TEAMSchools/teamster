from dagster import SensorResult, build_sensor_context

from teamster.libraries.core.resources import SSH_EDPLAN


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


def test_edplan_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.edplan.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_edplan=SSH_EDPLAN)
