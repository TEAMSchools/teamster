from dagster import DagsterInstance, build_schedule_context


def _test(schedule):
    context = build_schedule_context(instance=DagsterInstance.get())

    output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_grow_static_partition_asset_job_schedule():
    from teamster.code_locations.kipptaf.level_data.grow.schedules import (
        grow_static_partition_asset_job_schedule,
    )

    _test(grow_static_partition_asset_job_schedule)


def test_grow_static_runs_multiprocess_in_the_run_pod():
    from dagster_k8s.job import get_user_defined_k8s_config

    from teamster.code_locations.kipptaf.level_data.grow.schedules import (
        grow_static_partition_asset_job,
        grow_static_partition_asset_job_schedule,
    )

    assert (
        grow_static_partition_asset_job_schedule.job_name
        == grow_static_partition_asset_job.name
    )
    assert grow_static_partition_asset_job.executor_def is not None
    assert grow_static_partition_asset_job.executor_def.name == "multiprocess"

    # parse the tag the way the run launcher does
    config = get_user_defined_k8s_config(grow_static_partition_asset_job.tags or {})
    assert "memory" in config.container_config["resources"]["requests"]
