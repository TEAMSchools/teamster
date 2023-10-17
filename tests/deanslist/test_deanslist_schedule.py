from dagster import build_schedule_context

from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kippnewark.deanslist.schedules import multi_partition_asset_job_schedule


def test_schedule():
    context = build_schedule_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    output = multi_partition_asset_job_schedule()

    for o in output:
        context.log.info(o)
