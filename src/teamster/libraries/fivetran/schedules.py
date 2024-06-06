from dagster import ScheduleEvaluationContext, SkipReason, job, schedule
from dagster_fivetran import FivetranResource


@job
def fivetran_job():
    """Placeholder job"""


def build_fivetran_start_sync_schedule(
    code_location, connector_id, connector_name, cron_schedule, execution_timezone
):
    @schedule(
        name=f"{code_location}_fivetran_sync_{connector_name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=fivetran_job,
    )
    def _schedule(context: ScheduleEvaluationContext, fivetran: FivetranResource):
        fivetran.start_sync(connector_id=connector_id)
        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule


def build_fivetran_start_resync_schedule(
    code_location, connector_id, connector_name, cron_schedule, execution_timezone
):
    @schedule(
        name=f"{code_location}_fivetran_resync_{connector_name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=fivetran_job,
    )
    def _schedule(context: ScheduleEvaluationContext, fivetran: FivetranResource):
        fivetran.start_resync(connector_id=connector_id)
        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule
