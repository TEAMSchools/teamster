from dagster import build_sensor_context

from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kipptaf.dbt.sensors import dbt_code_version_sensor


def test_code_version_sensor():
    run_requests = dbt_code_version_sensor(
        context=build_sensor_context(
            instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
        )
    )

    print(run_requests)
