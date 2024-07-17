import json

import pendulum
from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.fivetran.sensors import fivetran_sync_status_sensor
from teamster.code_locations.kipptaf.resources import FIVETRAN_RESOURCE
from teamster.libraries.core.resources import BIGQUERY_RESOURCE


def test_fivetran_sync_status_sensor():
    cursor = {
        connector_id: pendulum.today().subtract(days=1).timestamp()
        for connector_id in [
            "sameness_cunning",
            "genuine_describing",
            "muskiness_cumulative",
            "bellows_curliness",
            "jinx_credulous",
            "regency_carrying",
        ]
    }

    context = build_sensor_context(
        cursor=json.dumps(obj=cursor), sensor_name=fivetran_sync_status_sensor.name
    )

    sensor_result = fivetran_sync_status_sensor(
        context=context, fivetran=FIVETRAN_RESOURCE, db_bigquery=BIGQUERY_RESOURCE
    )

    assert isinstance(sensor_result, SensorResult)

    context.log.info(msg=sensor_result.asset_events)
    assert len(sensor_result.asset_events) > 0
