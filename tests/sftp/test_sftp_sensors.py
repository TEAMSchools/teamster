from dagster import EnvVar, SensorResult, build_sensor_context
from teamster.core.ssh.resources import SSHConfigurableResource


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context()

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    context.log.info(result)

    assert len(result.run_requests) > 0


def test_sensor_edplan():
    from teamster.kippcamden.edplan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_edplan=SSHConfigurableResource(
            remote_host="secureftp.easyiep.com",
            username=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_USERNAME"),
            password=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.edplan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_edplan=SSHConfigurableResource(
            remote_host="secureftp.easyiep.com",
            username=EnvVar("KIPPNEWARK_EDPLAN_SFTP_USERNAME"),
            password=EnvVar("KIPPNEWARK_EDPLAN_SFTP_PASSWORD"),
        ),
    )


def test_sensor_titan():
    from teamster.kippcamden.titan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_titan=SSHConfigurableResource(
            remote_host="sftp.titank12.com",
            username=EnvVar("KIPPCAMDEN_TITAN_SFTP_USERNAME"),
            password=EnvVar("KIPPCAMDEN_TITAN_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.titan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_titan=SSHConfigurableResource(
            remote_host="sftp.titank12.com",
            username=EnvVar("KIPPNEWARK_TITAN_SFTP_USERNAME"),
            password=EnvVar("KIPPNEWARK_TITAN_SFTP_PASSWORD"),
        ),
    )


def test_sensor_iready():
    from teamster.kippmiami.iready.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_iready=SSHConfigurableResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.iready.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_iready=SSHConfigurableResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
    )


def test_sensor_renlearn():
    from teamster.kippmiami.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_renlearn=SSHConfigurableResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_renlearn=SSHConfigurableResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
        ),
    )


def test_sensor_achieve3k():
    from teamster.kipptaf.achieve3k.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_achieve3k=SSHConfigurableResource(
            remote_host="xfer.achieve3000.com",
            username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
            password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
        ),
    )


def test_sensor_clever_reports():
    from teamster.kipptaf.clever.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_clever_reports=SSHConfigurableResource(
            remote_host="sftp.clever.com",
            username=EnvVar("CLEVER_SFTP_USERNAME"),
            password=EnvVar("CLEVER_SFTP_PASSWORD"),
        ),
    )


""" doesn't work on codespaces
def test_sensor_adp():
    from teamster.kipptaf.adp.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_adp=SSHConfigurableResource(
            remote_host="sftp.kippnj.org",
            username=EnvVar("ADP_SFTP_USERNAME"),
            password=EnvVar("ADP_SFTP_PASSWORD"),
        ),
    )
"""
