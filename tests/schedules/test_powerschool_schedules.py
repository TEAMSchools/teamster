from dagster import DagsterInstance, build_schedule_context

from teamster.core.resources import DB_POWERSCHOOL, get_ssh_resource_powerschool
from teamster.kippnewark.powerschool.schedules import last_modified_schedule


def test_schedule():
    with build_schedule_context(instance=DagsterInstance.get()) as context:
        output = last_modified_schedule(
            context=context,
            ssh_powerschool=get_ssh_resource_powerschool("teamacademy.clgpstest.com"),
            db_powerschool=DB_POWERSCHOOL,
        )

        for o in output:
            context.log.info(o)
