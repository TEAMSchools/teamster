from dagster import DagsterInstance, build_schedule_context

from teamster.kippcamden.deanslist.schedules import (
    deanslist_comm_log_midday_job_schedule,
)


def test_schedule():
    context = build_schedule_context(instance=DagsterInstance.get())

    output = deanslist_comm_log_midday_job_schedule(context=context)

    for o in output:  # type: ignore
        context.log.info(o)
