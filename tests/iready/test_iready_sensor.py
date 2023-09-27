from dagster import EnvVar, build_sensor_context, instance_for_test

from teamster.core.iready.sensors import build_sftp_sensor
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.kippmiami import LOCAL_TIMEZONE as kippmiami_local_timezone
from teamster.kippmiami.iready.assets import sftp_assets as kippmiami_sftp_assets

SSH_IREADY = SSHConfigurableResource(
    remote_host="prod-sftp-1.aws.cainc.com",
    username=EnvVar("IREADY_SFTP_USERNAME"),
    password=EnvVar("IREADY_SFTP_PASSWORD"),
)


def _test(sensor):
    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance)

        sensor_results = sensor(context=context, ssh_iready=SSH_IREADY)

        for result in sensor_results:
            context.log.info(result)


def test_sensor_kippmiami():
    sensor = build_sftp_sensor(
        code_location="kippmiami",
        source_system="iready",
        timezone=kippmiami_local_timezone,
        asset_defs=kippmiami_sftp_assets,
    )

    _test(sensor=sensor)
