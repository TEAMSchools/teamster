from dagster import build_sensor_context

from teamster.core.powerschool.sensors import build_powerschool_sensor
from teamster.core.resources import DB_POWERSCHOOL, get_ssh_resource_powerschool
from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kippnewark.powerschool.assets import partition_assets
from teamster.staging import LOCAL_TIMEZONE


def test_powerschool_sensor():
    context = build_sensor_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    dynamic_partition_sensor = build_powerschool_sensor(
        name="test",
        asset_selection=partition_assets,
        asset_defs=partition_assets,
        execution_timezone=LOCAL_TIMEZONE,
    )

    sensor_results = dynamic_partition_sensor(
        context=context,
        ssh_powerschool=get_ssh_resource_powerschool("teamacademy.clgpstest.com"),
        db_powerschool=DB_POWERSCHOOL,
    )

    for result in sensor_results:
        context.log.info(result)
