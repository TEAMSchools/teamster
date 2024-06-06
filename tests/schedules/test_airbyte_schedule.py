from dagster import build_schedule_context

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE
from teamster.libraries.airbyte.schedules import build_airbyte_start_sync_schedule


def test_schedule():
    airbyte_start_sync_schedule = build_airbyte_start_sync_schedule(
        code_location="staging",
        connection_id="",
        connection_name="test",
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
    )

    context = build_schedule_context()

    output = airbyte_start_sync_schedule(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    assert output is not None
    for o in output:
        context.log.info(o)
