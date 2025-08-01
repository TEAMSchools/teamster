from dagster import SensorResult, build_sensor_context


def _test_sensor(sftp_sensor, ssh_deanslist):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, ssh_deanslist=ssh_deanslist)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


def test_deanslist_sftp_sensor_kipptaf():
    from teamster.code_locations.kipptaf.deanslist.sensors import deanslist_sftp_sensor
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_DEANSLIST

    _test_sensor(
        sftp_sensor=deanslist_sftp_sensor, ssh_deanslist=SSH_RESOURCE_DEANSLIST
    )
