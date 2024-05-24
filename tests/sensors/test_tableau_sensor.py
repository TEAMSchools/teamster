import json

from dagster import build_sensor_context

from teamster.kipptaf.resources import TABLEAU_SERVER_RESOURCE
from teamster.kipptaf.tableau.sensors import tableau_asset_sensor


def test_tableau_asset_sensor():
    cursor = {}

    context = build_sensor_context(
        cursor=json.dumps(obj=cursor), sensor_name=tableau_asset_sensor.name
    )

    sensor_result = tableau_asset_sensor(
        context=context, tableau=TABLEAU_SERVER_RESOURCE
    )

    asset_events = sensor_result.asset_events

    context.log.info(msg=asset_events)
    assert len(asset_events) > 0
