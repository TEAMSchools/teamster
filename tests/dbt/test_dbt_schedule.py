from dagster import build_schedule_context

from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kipptaf.dbt.schedules import dbt_code_version_schedule


def test_schedule():
    context = build_schedule_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    output = dbt_code_version_schedule(context=context)

    context.log.info(output)
