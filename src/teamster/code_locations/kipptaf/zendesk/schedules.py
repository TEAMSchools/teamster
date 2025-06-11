from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.zendesk.jobs import zendesk_user_sync_op_job

zendesk_user_sync_schedule = ScheduleDefinition(
    job=zendesk_user_sync_op_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    zendesk_user_sync_schedule,
]
