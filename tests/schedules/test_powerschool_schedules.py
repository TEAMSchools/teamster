from dagster import build_schedule_context

from teamster.core.resources import DB_POWERSCHOOL, get_ssh_resource_powerschool
from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kippnewark.powerschool.schedules import last_modified_schedule


def test_schedule():
    context = build_schedule_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    output = last_modified_schedule(
        context=context,
        ssh_powerschool=get_ssh_resource_powerschool("teamacademy.clgpstest.com"),
        db_powerschool=DB_POWERSCHOOL,
    )

    for o in output:
        context.log.info(o)
