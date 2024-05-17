from dagster import build_schedule_context

from teamster.kipptaf import LOCAL_TIMEZONE
from teamster.kipptaf.airbyte.schedules import build_airbyte_start_sync_schedule
from teamster.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE


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

    for o in output:  # type: ignore
        context.log.info(o)
