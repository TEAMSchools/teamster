from dagster import build_schedule_context

from teamster.kipptaf.airbyte.schedules import build_airbyte_start_sync_schedule
from teamster.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE
from teamster.staging import CODE_LOCATION, LOCAL_TIMEZONE


def test_schedule():
    airbyte_start_sync_schedule = build_airbyte_start_sync_schedule(
        code_location=CODE_LOCATION,
        connection_id="",
        connection_name="test",
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
    )

    context = build_schedule_context()

    output = airbyte_start_sync_schedule(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    for o in output:
        context.log.info(o)
