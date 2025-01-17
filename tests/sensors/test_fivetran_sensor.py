import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.fivetran.sensors import (
    fivetran_connector_sync_status_sensor,
)
from teamster.code_locations.kipptaf.resources import FIVETRAN_RESOURCE
from teamster.core.resources import BIGQUERY_RESOURCE


def test_fivetran_connector_sync_status_sensor_initial():
    sensor_result = fivetran_connector_sync_status_sensor(
        context=build_sensor_context(),
        fivetran=FIVETRAN_RESOURCE,
        db_bigquery=BIGQUERY_RESOURCE,
    )

    assert isinstance(sensor_result, SensorResult)

    assert len(sensor_result.asset_events) > 0
    print(sensor_result.asset_events)

    assert sensor_result.cursor is not None
    print(sensor_result.cursor)


def test_fivetran_connector_sync_status_sensor_cursor():
    cursor = {
        "connectors": {
            "sameness_cunning": 1723450048.417,
            "bellows_curliness": 1723449958.987,
            "regency_carrying": 1723457999.419,
            "muskiness_cumulative": 1723457833.448,
        },
        "assets": {},
    }

    sensor_result = fivetran_connector_sync_status_sensor(
        context=build_sensor_context(cursor=json.dumps(obj=cursor)),
        fivetran=FIVETRAN_RESOURCE,
        db_bigquery=BIGQUERY_RESOURCE,
    )

    if isinstance(sensor_result, SensorResult):
        assert len(sensor_result.asset_events) > 0
        print(sensor_result.asset_events)

        assert sensor_result.cursor is not None
        print(sensor_result.cursor)
