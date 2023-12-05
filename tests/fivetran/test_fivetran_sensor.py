import json

from dagster import EnvVar, build_sensor_context
from dagster_fivetran import FivetranResource
from dagster_gcp import BigQueryResource

from teamster import GCS_PROJECT_NAME
from teamster.kipptaf.fivetran.sensors import fivetran_sync_status_sensor

CURSOR = {
    "sameness_cunning": 1698296400,  # adp_workforce_now
    "genuine_describing": 1698296400,
    "muskiness_cumulative": 1698296400,
    "bellows_curliness": 1698296400,
    "jinx_credulous": 1698296400,
    "aspirate_uttering": 1698296400,
    "regency_carrying": 1698296400,
}


def test_process_new_users_sensor():
    run_requests = fivetran_sync_status_sensor(
        context=build_sensor_context(cursor=json.dumps(obj=CURSOR)),
        fivetran=FivetranResource(
            api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET")
        ),
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
    )

    print(run_requests)
