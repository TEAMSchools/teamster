import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.resources import TABLEAU_SERVER_RESOURCE
from teamster.code_locations.kipptaf.tableau.sensors import tableau_asset_sensor


def test_tableau_asset_sensor():
    cursor = {}

    context = build_sensor_context(
        cursor=json.dumps(obj=cursor), sensor_name=tableau_asset_sensor.name
    )

    sensor_result = tableau_asset_sensor(
        context=context, tableau=TABLEAU_SERVER_RESOURCE
    )

    assert isinstance(sensor_result, SensorResult)

    context.log.info(msg=sensor_result.asset_events)
    assert len(sensor_result.asset_events) > 0
