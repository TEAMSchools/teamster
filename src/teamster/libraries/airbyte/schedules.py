from dagster import ScheduleEvaluationContext, SkipReason, _check, job, schedule
from dagster_airbyte import AirbyteCloudResource


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
    def _schedule(context: ScheduleEvaluationContext, airbyte: AirbyteCloudResource):
        job_sync = _check.not_none(
            airbyte.make_request(
                endpoint="/jobs",
                data={"connectionId": connection_id, "jobType": "sync"},
            )
        )

        context.log.info(
            f"Job {job_sync["jobId"]} {job_sync["status"]} for {connection_id}"
        )

        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule
