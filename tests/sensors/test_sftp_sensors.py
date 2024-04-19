import json

from dagster import SensorResult, build_sensor_context

from teamster.core.resources import (
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_IREADY,
    SSH_RENLEARN,
    SSH_TITAN,
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
    from teamster.kippnewark.edplan.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_edplan=SSH_EDPLAN)


def test_sensor_titan():
    from teamster.kippcamden.titan.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_titan=SSH_TITAN)


def test_sensor_iready():
    from teamster.kippmiami.iready.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_iready=SSH_IREADY)


def test_sensor_renlearn():
    from teamster.kippnewark.renlearn.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_renlearn=SSH_RENLEARN)


def test_sensor_deanslist():
    from teamster.kipptaf.deanslist.sensors import deanslist_sftp_sensor
    from teamster.kipptaf.resources import SSH_RESOURCE_DEANSLIST

    _test_sensor(
        sftp_sensor=deanslist_sftp_sensor, ssh_deanslist=SSH_RESOURCE_DEANSLIST
    )


def test_sensor_adp_payroll():
    from teamster.kipptaf.adp.payroll.sensors import adp_payroll_sftp_sensor

    _test_sensor(sftp_sensor=adp_payroll_sftp_sensor, ssh_couchdrop=SSH_COUCHDROP)


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
