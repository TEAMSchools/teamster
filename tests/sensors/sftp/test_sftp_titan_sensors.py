from dagster import EnvVar, SensorResult, build_sensor_context

from teamster.libraries.ssh.resources import SSHResource


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


def test_titan_sftp_sensor_kippcamden():
    from teamster.code_locations.kippcamden.titan.sensors import titan_sftp_sensor

    _test_sensor(
        sftp_sensor=titan_sftp_sensor,
        ssh_titan=SSHResource(
            remote_host="104.154.118.214",
            username=EnvVar("TITAN_SFTP_USERNAME_KIPPCAMDEN"),
            password=EnvVar("TITAN_SFTP_PASSWORD_KIPPCAMDEN"),
        ),
    )


def test_titan_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.titan.sensors import titan_sftp_sensor

    _test_sensor(
        sftp_sensor=titan_sftp_sensor,
        ssh_titan=SSHResource(
            remote_host="104.154.118.214",
            username=EnvVar("TITAN_SFTP_USERNAME_KIPPNEWARK"),
            password=EnvVar("TITAN_SFTP_PASSWORD_KIPPNEWARK"),
        ),
    )
