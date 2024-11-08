from dagster import DagsterInstance, build_schedule_context

from teamster.code_locations.kipptaf.schoolmint.grow.schedules import (
    schoolmint_grow_observations_asset_job_schedule,
    schoolmint_grow_static_partition_asset_job_schedule,
)


def _test(schedule):
    context = build_schedule_context(instance=DagsterInstance.get())

    output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_schoolmint_grow_observations_asset_job_schedule():
    _test(schoolmint_grow_observations_asset_job_schedule)


def test_schoolmint_grow_static_partition_asset_job_schedule():
    _test(schoolmint_grow_static_partition_asset_job_schedule)
