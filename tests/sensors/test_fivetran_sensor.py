import json

from dagster import build_sensor_context

from teamster.core.resources import BIGQUERY_RESOURCE
from teamster.kipptaf.fivetran.sensors import fivetran_sync_status_sensor
from teamster.kipptaf.resources import FIVETRAN_RESOURCE


def test_fivetran_sync_status_sensor():
    cursor = {
        # "sameness_cunning": 1698296400,  # adp_workforce_now
        # "genuine_describing": 1698296400,
        # "muskiness_cumulative": 1698296400,
        # "bellows_curliness": 1698296400,
        # "jinx_credulous": 1698296400,
        # "aspirate_uttering": 1698296400,
        # "regency_carrying": 1698296400,
    }

    sensor_result = fivetran_sync_status_sensor(
        context=build_sensor_context(
            cursor=json.dumps(obj=cursor), sensor_name=fivetran_sync_status_sensor.name
        ),
        fivetran=FIVETRAN_RESOURCE,
        db_bigquery=BIGQUERY_RESOURCE,
    )

    # trunk-ignore(bandit/B101)
    assert len(sensor_result.run_requests) > 0  # type: ignore
