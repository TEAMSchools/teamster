from dagster import DagsterInstance, build_schedule_context

from teamster.code_locations.kippcamden.deanslist.schedules import (
    deanslist_midday_commlog_job_schedule,
)


def test_schedule():
    context = build_schedule_context(instance=DagsterInstance.get())

    output = deanslist_midday_commlog_job_schedule(context=context)

    context.log.info(output)
