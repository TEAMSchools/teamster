from dagster import DagsterInstance, build_schedule_context


def test_schedule():
    from teamster.code_locations.kipptaf.adp.workforce_now.api.schedules import (
        adp_workforce_now_api_workers_asset_schedule,
    )

    context = build_schedule_context(instance=DagsterInstance.get())

    output = adp_workforce_now_api_workers_asset_schedule(context=context)

    for o in output:
        context.log.info(o)
