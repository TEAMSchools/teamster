from dagster import ScheduleEvaluationContext, SkipReason, job, schedule
from dagster_airbyte import AirbyteCloudWorkspace
from dagster_airbyte.translator import AirbyteJob


def build_airbyte_start_sync_schedule(
    code_location, connection_id, connection_name, cron_schedule, execution_timezone
):
    @job(name=f"{code_location}_airbyte_sync_{connection_name}_job")
    def _job():
        """Placehoder job"""

    @schedule(
        name=f"{_job.name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=_job,
    )
    def _schedule(context: ScheduleEvaluationContext, airbyte: AirbyteCloudWorkspace):
        airbyte_client = airbyte.get_client()

        start_job_details = airbyte_client.start_sync_job(connection_id)

        job = AirbyteJob.from_job_details(job_details=start_job_details)

        context.log.info(f"{job.id=} initialized for {connection_id=}.")

        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule
