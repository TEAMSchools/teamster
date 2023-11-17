import json

from dagster import EnvVar, SensorResult, build_sensor_context
from dagster_ssh import SSHResource


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context()

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    distinct_asset_keys = list(
        set(
            [
                "_".join(a)
                for rr in result.run_requests
                for assets in rr.asset_selection
                for a in assets
            ]
        )
    )

    assert len(distinct_asset_keys) == len(json.loads(result.cursor).keys())


def test_sensor_edplan():
    from teamster.kippcamden.edplan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_edplan=SSHResource(
            remote_host="secureftp.easyiep.com",
            username=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_USERNAME"),
            password=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.edplan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_edplan=SSHResource(
            remote_host="secureftp.easyiep.com",
            username=EnvVar("KIPPNEWARK_EDPLAN_SFTP_USERNAME"),
            password=EnvVar("KIPPNEWARK_EDPLAN_SFTP_PASSWORD"),
        ),
    )


def test_sensor_titan():
    from teamster.kippcamden.titan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_titan=SSHResource(
            remote_host="sftp.titank12.com",
            username=EnvVar("KIPPCAMDEN_TITAN_SFTP_USERNAME"),
            password=EnvVar("KIPPCAMDEN_TITAN_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.titan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_titan=SSHResource(
            remote_host="sftp.titank12.com",
            username=EnvVar("KIPPNEWARK_TITAN_SFTP_USERNAME"),
            password=EnvVar("KIPPNEWARK_TITAN_SFTP_PASSWORD"),
        ),
    )


def test_sensor_iready():
    ssh_iready = SSHResource(
        remote_host="prod-sftp-1.aws.cainc.com",
        username=EnvVar("IREADY_SFTP_USERNAME"),
        password=EnvVar("IREADY_SFTP_PASSWORD"),
    )

    from teamster.kippmiami.iready.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_iready=ssh_iready)

    from teamster.kippnewark.iready.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_iready=ssh_iready)


def test_sensor_renlearn():
    from teamster.kippmiami.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_renlearn=SSHResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
    )

    from teamster.kippnewark.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_renlearn=SSHResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
        ),
    )


def test_sensor_achieve3k():
    from teamster.kipptaf.achieve3k.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_achieve3k=SSHResource(
            remote_host="xfer.achieve3000.com",
            username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
            password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
        ),
    )


def test_sensor_clever_reports():
    from teamster.kipptaf.clever.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_clever_reports=SSHResource(
            remote_host="reports-sftp.clever.com",
            username=EnvVar("CLEVER_REPORTS_SFTP_USERNAME"),
            password=EnvVar("CLEVER_REPORTS_SFTP_PASSWORD"),
        ),
    )


# ip restricted
def test_sensor_adp():
    from teamster.kipptaf.adp.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_adp_workforce_now=SSHResource(
            remote_host="sftp.kippnj.org",
            username=EnvVar("ADP_SFTP_USERNAME"),
            password=EnvVar("ADP_SFTP_PASSWORD"),
        ),
    )
