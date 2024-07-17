from typing import Generator

from dagster import DagsterInstance, _check, build_schedule_context

from teamster.code_locations.kipptaf.adp.workforce_now.api.schedules import (
    adp_wfn_api_workers_asset_schedule,
)


def test_schedule():
    context = build_schedule_context(instance=DagsterInstance.get())

    output = _check.inst(
        obj=adp_wfn_api_workers_asset_schedule(context=context), ttype=Generator
    )

    for o in output:
        context.log.info(o)
