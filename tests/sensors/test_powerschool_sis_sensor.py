from dagster import DagsterInstance, SensorResult, _check, build_sensor_context

from teamster.core.resources import (
    get_db_powerschool_resource,
    get_ssh_powerschool_resource,
)


def _test(sensor, ssh_powerschool, db_powerschool):
    with build_sensor_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        ),
        resources={
            "ssh_powerschool": ssh_powerschool,
            "db_powerschool": db_powerschool,
        },
    ) as context:
        sensor_results = sensor(context=context)

    sensor_results = _check.inst(obj=sensor_results, ttype=SensorResult)

    assert sensor_results.run_requests is not None

    for result in sensor_results.run_requests:
        context.log.info(result)


def test_powerschool_sis_sensor_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool.sensors import (
        powerschool_asset_sensor,
    )

    _test(
        sensor=powerschool_asset_sensor,
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_powerschool_sis_sensor_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool.sensors import (
        powerschool_asset_sensor,
    )

    _test(
        sensor=powerschool_asset_sensor,
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_powerschool_sis_sensor_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool.sensors import (
        powerschool_asset_sensor,
    )

    _test(
        sensor=powerschool_asset_sensor,
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )
