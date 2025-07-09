from dagster import DagsterInstance, build_schedule_context


def _test(schedule):
    context = build_schedule_context(instance=DagsterInstance.get())

    output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_grow_observations_asset_job_schedule():
    from teamster.code_locations.kipptaf.level_data.grow.schedules import (
        grow_observations_asset_job_schedule,
    )

    _test(grow_observations_asset_job_schedule)


def test_grow_static_partition_asset_job_schedule():
    from teamster.code_locations.kipptaf.level_data.grow.schedules import (
        grow_static_partition_asset_job_schedule,
    )

    _test(grow_static_partition_asset_job_schedule)
