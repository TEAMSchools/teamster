from dagster import SensorResult, build_sensor_context

from teamster.libraries.core.resources import SSH_COUCHDROP


def _test_sensor(sftp_sensor, **kwargs):
    context = build_sensor_context(sensor_name=sftp_sensor.name)

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


def test_couchdrop_sftp_sensor_kipptaf():
    from teamster.code_locations.kipptaf.couchdrop.sensors import couchdrop_sftp_sensor

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor, ssh_couchdrop=SSH_COUCHDROP)


def test_couchdrop_sftp_sensor_kippcamden():
    from teamster.code_locations.kippcamden.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor, ssh_couchdrop=SSH_COUCHDROP)


def test_couchdrop_sftp_sensor_kippmiami():
    from teamster.code_locations.kippmiami.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor, ssh_couchdrop=SSH_COUCHDROP)


def test_couchdrop_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(sftp_sensor=couchdrop_sftp_sensor, ssh_couchdrop=SSH_COUCHDROP)


def test_adp_payroll_sftp_sensor():
    from teamster.code_locations.kipptaf.adp.payroll.sensors import (
        adp_payroll_sftp_sensor,
    )

    _test_sensor(sftp_sensor=adp_payroll_sftp_sensor, ssh_couchdrop=SSH_COUCHDROP)
