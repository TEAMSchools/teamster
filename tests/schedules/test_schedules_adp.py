from dagster import DagsterInstance, build_schedule_context


def test_schedule():
    from teamster.code_locations.kipptaf.adp.workforce_now.api.schedules import (
        adp_workforce_now_api_workers_asset_schedule,
    )

    context = build_schedule_context(instance=DagsterInstance.get())

    output = adp_workforce_now_api_workers_asset_schedule(context=context)

    # trunk-ignore(pyright/reportGeneralTypeIssues)
    # trunk-ignore(pyright/reportOptionalIterable)
    for o in output:
        context.log.info(o)


def test_adp_workers_schedule_runs_in_process():
    from teamster.code_locations.kipptaf.adp.workforce_now.api.schedules import (
        adp_workforce_now_api_workers_asset_schedule as schedule,
    )
    from teamster.code_locations.kipptaf.adp.workforce_now.api.schedules import (
        adp_workforce_now_workers_asset_job as job,
    )

    assert schedule.job_name == "kipptaf__adp__workforce_now__workers_asset_job"
    assert job.executor_def is not None
    assert job.executor_def.name == "in_process"
