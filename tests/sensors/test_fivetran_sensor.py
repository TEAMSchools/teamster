import json

import pendulum
from dagster import build_sensor_context

from teamster.core.resources import BIGQUERY_RESOURCE
from teamster.kipptaf.fivetran.sensors import fivetran_sync_status_sensor
from teamster.kipptaf.resources import FIVETRAN_RESOURCE


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

    asset_events = sensor_result.asset_events  # type: ignore

    context.log.info(msg=asset_events)
    assert len(asset_events) > 0
