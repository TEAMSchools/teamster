from dagster import EnvVar, SensorResult, build_sensor_context

from teamster.libraries.ssh.resources import SSHResource


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


def test_renlearn_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_renlearn=SSHResource(
            remote_host=EnvVar("RENLEARN_SFTP_HOST"),
            username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPNJ"),
            password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPNJ"),
        ),
    )


def test_renlearn_sftp_sensor_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_renlearn=SSHResource(
            remote_host=EnvVar("RENLEARN_SFTP_HOST"),
            username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
            password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
        ),
    )
