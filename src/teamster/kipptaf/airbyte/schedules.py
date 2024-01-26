from dagster import ScheduleEvaluationContext, SkipReason, job, schedule
from dagster_airbyte import AirbyteCloudResource

from .. import CODE_LOCATION, LOCAL_TIMEZONE


@job
def airbyte_job():
    ...


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


zendesk_start_sync_schedule = build_airbyte_start_sync_schedule(
    code_location=CODE_LOCATION,
    connection_id="ee23720c-c82f-45be-ab40-f72dcf8ac3cd",
    connection_name="zendesk",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

kippadb_start_sync_schedule = build_airbyte_start_sync_schedule(
    code_location=CODE_LOCATION,
    connection_id="e4856fb7-1f97-4bcd-bc4e-e616c5ae4e52",
    connection_name="kippadb",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    kippadb_start_sync_schedule,
    zendesk_start_sync_schedule,
]
