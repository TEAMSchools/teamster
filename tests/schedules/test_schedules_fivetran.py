from dagster import SkipReason, build_schedule_context

from teamster.code_locations.kipptaf.fivetran.schedules import (
    coupa_start_sync_schedule,
    illuminate_start_sync_schedule,
    illuminate_xmin_start_sync_schedule,
)
from teamster.code_locations.kipptaf.resources import FIVETRAN_RESOURCE


def test_fivetran_coupa_start_sync_schedule():
    context = build_schedule_context()

    output = coupa_start_sync_schedule(context=context, fivetran=FIVETRAN_RESOURCE)

    assert isinstance(output, SkipReason)

    context.log.info(output)


def test_fivetran_illuminate_start_sync_schedule():
    context = build_schedule_context()

    output = illuminate_start_sync_schedule(context=context, fivetran=FIVETRAN_RESOURCE)

    assert isinstance(output, SkipReason)

    context.log.info(output)


def test_fivetran_illuminate_xmin_start_sync_schedule():
    context = build_schedule_context()

    output = illuminate_xmin_start_sync_schedule(
        context=context, fivetran=FIVETRAN_RESOURCE
    )

    assert isinstance(output, SkipReason)

    context.log.info(output)
