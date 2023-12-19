import json

from dagster import SensorResult, build_sensor_context

from teamster.core.resources import (
    SSH_IREADY,
    get_ssh_resource_edplan,
    get_ssh_resource_renlearn,
    get_ssh_resource_titan,
)


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    distinct_asset_keys = list(
        set(
            [
                "_".join(a)
                for rr in result.run_requests  # type: ignore
                for assets in rr.asset_selection  # type: ignore
                for a in assets
            ]
        )
    )

    assert len(distinct_asset_keys) == len(json.loads(s=result.cursor).keys())  # type: ignore


def test_sensor_edplan():
    from teamster.kippcamden.edplan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor, ssh_edplan=get_ssh_resource_edplan("KIPPCAMDEN")
    )

    from teamster.kippnewark.edplan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor, ssh_edplan=get_ssh_resource_edplan("KIPPNEWARK")
    )


def test_sensor_titan():
    from teamster.kippcamden.titan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor, ssh_titan=get_ssh_resource_titan("KIPPCAMDEN")
    )

    from teamster.kippnewark.titan.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor, ssh_titan=get_ssh_resource_titan("KIPPNEWARK")
    )


def test_sensor_iready():
    from teamster.kippmiami.iready.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_iready=SSH_IREADY)

    from teamster.kippnewark.iready.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_iready=SSH_IREADY)


def test_sensor_renlearn():
    from teamster.kippmiami.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor, ssh_renlearn=get_ssh_resource_renlearn("KIPPMIAMI")
    )

    from teamster.kippnewark.renlearn.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor, ssh_renlearn=get_ssh_resource_renlearn("KIPPNJ")
    )


def test_sensor_achieve3k():
    from teamster.kipptaf.achieve3k.sensors import achieve3k_sftp_sensor
    from teamster.kipptaf.resources import SSH_RESOURCE_ACHIEVE3K

    _test_sensor(
        sftp_sensor=achieve3k_sftp_sensor, ssh_achieve3k=SSH_RESOURCE_ACHIEVE3K
    )


def test_sensor_clever_reports():
    from teamster.kipptaf.clever.sensors import clever_reports_sftp_sensor
    from teamster.kipptaf.resources import SSH_RESOURCE_CLEVER_REPORTS

    _test_sensor(
        sftp_sensor=clever_reports_sftp_sensor,
        ssh_clever_reports=SSH_RESOURCE_CLEVER_REPORTS,
    )


def test_sensor_deanslist():
    from teamster.kipptaf.deanslist.sensors import deanslist_sftp_sensor
    from teamster.kipptaf.resources import SSH_RESOURCE_DEANSLIST

    _test_sensor(
        sftp_sensor=deanslist_sftp_sensor, ssh_deanslist=SSH_RESOURCE_DEANSLIST
    )


"""
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
"""
