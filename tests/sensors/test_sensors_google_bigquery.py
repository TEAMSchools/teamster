import json

from dagster import SensorResult, build_sensor_context
from dagster_shared import check

from teamster.core.resources import BIGQUERY_RESOURCE


def test_bigquery_table_sensor():
    from teamster.code_locations.kipptaf.google.bigquery.sensors import (
        bigquery_table_modified_sensor,
    )

    context = build_sensor_context()

    sensor_result = bigquery_table_modified_sensor(
        context=context, db_bigquery=BIGQUERY_RESOURCE
    )

    sensor_result = check.inst(obj=sensor_result, ttype=SensorResult)

    assert sensor_result.asset_events is not None

    for asset_event in sensor_result.asset_events:
        context.log.info(msg=asset_event)

    context.log.info(msg=sensor_result.cursor)


def test_bigquery_table_sensor_cursor_offset():
    """Guards the cursor migration: a cursor written before chunking existed must
    still load, the resume offset must round-trip, and the reserved key must not
    be able to collide with a generated asset identifier.
    """
    from teamster.code_locations.kipptaf.google.bigquery.sensors import (
        OFFSET_CURSOR_KEY,
        asset_selection,
        bigquery_table_modified_sensor,
    )

    # a cursor in the pre-chunking shape: asset identifiers only, no offset key
    legacy_identifier = asset_selection[0].key.to_python_identifier()

    context = build_sensor_context(
        cursor=json.dumps({legacy_identifier: 1.0}),
    )

    sensor_result = check.inst(
        obj=bigquery_table_modified_sensor(
            context=context, db_bigquery=BIGQUERY_RESOURCE
        ),
        ttype=SensorResult,
    )

    cursor = json.loads(check.not_none(value=sensor_result.cursor))

    assert OFFSET_CURSOR_KEY in cursor
    assert isinstance(cursor[OFFSET_CURSOR_KEY], int)
    assert 0 <= cursor[OFFSET_CURSOR_KEY] < len(asset_selection)

    assert OFFSET_CURSOR_KEY not in {
        spec.key.to_python_identifier() for spec in asset_selection
    }
