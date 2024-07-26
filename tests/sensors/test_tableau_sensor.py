import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.resources import TABLEAU_SERVER_RESOURCE
from teamster.code_locations.kipptaf.tableau.sensors import tableau_asset_sensor


def test_tableau_asset_sensor():
    cursor = {}

    with build_sensor_context(
        sensor_name=tableau_asset_sensor.name,
        resources={"tableau": TABLEAU_SERVER_RESOURCE},
        cursor=json.dumps(obj=cursor),
    ) as context:
        sensor_result = tableau_asset_sensor(context=context)

    assert isinstance(sensor_result, SensorResult)

    assert len(sensor_result.asset_events) > 0
