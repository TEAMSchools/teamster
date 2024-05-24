from dagster import ScheduleEvaluationContext, SkipReason, job, schedule
from dagster_airbyte import AirbyteCloudResource


@job
def airbyte_job():
    """Placehoder job"""


def build_airbyte_start_sync_schedule(
    code_location, connection_id, connection_name, cron_schedule, execution_timezone
):
    @schedule(
        name=f"{code_location}_airbyte_sync_{connection_name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=airbyte_job,
    )  # type: ignore
    def _schedule(context: ScheduleEvaluationContext, airbyte: AirbyteCloudResource):
        job_details = airbyte.start_sync(connection_id)

        job_id = job_details.get("job", {}).get("id")  # type: ignore

        context.log.info(f"Job {job_id} initialized for connection_id={connection_id}.")

        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule
