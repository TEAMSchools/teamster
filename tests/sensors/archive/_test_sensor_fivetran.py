"""import json

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
        },
        "assets": {
            "kipptaf__coupa__address": 1710781408.472,
            "kipptaf__coupa__business_group": 1715112208.086,
            "kipptaf__coupa__role": 1723449855.899,
            "kipptaf__coupa__user": 1723449856.883,
            "kipptaf__coupa__user_business_group_mapping": 1723449880.422,
            "kipptaf__coupa__user_role_mapping": 1723449869.48,
        },
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
"""
