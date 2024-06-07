from dagster import build_schedule_context

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.resources import FIVETRAN_RESOURCE
from teamster.libraries.fivetran.schedules import (
    build_fivetran_start_resync_schedule,
    build_fivetran_start_sync_schedule,
)


def test_sync_schedule():
    fivetran_start_sync_schedule = build_fivetran_start_sync_schedule(
        code_location="staging",
        connector_id="",
        connector_name="test",
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
    )

    context = build_schedule_context()

    output = fivetran_start_sync_schedule(context=context, fivetran=FIVETRAN_RESOURCE)

    assert output is not None

    for o in output:
        context.log.info(o)


def test_resync_schedule():
    fivetran_start_sync_schedule = build_fivetran_start_resync_schedule(
        code_location="staging",
        connector_id="",
        connector_name="test",
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
    )

    context = build_schedule_context()

    output = fivetran_start_sync_schedule(context=context, fivetran=FIVETRAN_RESOURCE)

    assert output is not None
    for o in output:
        context.log.info(o)
