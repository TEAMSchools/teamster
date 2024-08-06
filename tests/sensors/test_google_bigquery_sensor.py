from dagster import SensorResult, _check, build_sensor_context

from teamster.code_locations.kipptaf._google.bigquery.sensors import (
    bigquery_table_modified_sensor,
)
from teamster.core.resources import BIGQUERY_RESOURCE


def test_bigquery_table_sensor():
    context = build_sensor_context()

    sensor_result = bigquery_table_modified_sensor(
        context=context, db_bigquery=BIGQUERY_RESOURCE
    )

    sensor_result = _check.inst(obj=sensor_result, ttype=SensorResult)

    assert sensor_result.asset_events is not None

    for asset_event in sensor_result.asset_events:
        context.log.info(msg=asset_event)

    context.log.info(msg=sensor_result.cursor)
