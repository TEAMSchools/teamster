from dagster import SkipReason, build_schedule_context


def test_kippadb_start_sync_schedule():
    from teamster.code_locations.kipptaf.airbyte.schedules import (
        kippadb_start_sync_schedule,
    )
    from teamster.code_locations.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE

    context = build_schedule_context()

    output = kippadb_start_sync_schedule(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    assert isinstance(output, SkipReason)

    context.log.info(output)


def test_zendesk_start_sync_schedule():
    from teamster.code_locations.kipptaf.airbyte.schedules import (
        zendesk_start_sync_schedule,
    )
    from teamster.code_locations.kipptaf.resources import AIRBYTE_CLOUD_RESOURCE

    context = build_schedule_context()

    output = zendesk_start_sync_schedule(
        context=context, airbyte=AIRBYTE_CLOUD_RESOURCE
    )

    assert isinstance(output, SkipReason)

    context.log.info(output)
