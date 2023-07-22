from dagster import EnvVar, build_sensor_context
from dagster_fivetran import FivetranResource
from dagster_gcp import BigQueryResource

from teamster.kipptaf import GCS_PROJECT_NAME
from teamster.kipptaf.fivetran.sensors import fivetran_sync_monitor_sensor


def test_process_new_users_sensor():
    context = build_sensor_context()

    run_requests = fivetran_sync_monitor_sensor(
        context,
        fivetran=FivetranResource(
            api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET")
        ),
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
    )

    print(run_requests)
