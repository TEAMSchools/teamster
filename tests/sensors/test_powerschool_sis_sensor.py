from dagster import DagsterInstance, build_sensor_context

from teamster.core.resources import DB_POWERSCHOOL, SSH_POWERSCHOOL
from teamster.kippnewark import LOCAL_TIMEZONE
from teamster.kippnewark.powerschool.assets import partition_assets
from teamster.powerschool.sis.sensors import build_powerschool_sensor


def test_powerschool_sensor():
    context = build_sensor_context(instance=DagsterInstance.get())

    dynamic_partition_sensor = build_powerschool_sensor(
        name="test",
        asset_selection=partition_assets,
        asset_defs=partition_assets,
        execution_timezone=LOCAL_TIMEZONE,
        max_runtime_seconds=None,
    )

    sensor_results = dynamic_partition_sensor(
        context=context,
        ssh_powerschool=SSH_POWERSCHOOL,
        db_powerschool=DB_POWERSCHOOL,
    )

    for result in sensor_results:  # type: ignore
        context.log.info(result)
