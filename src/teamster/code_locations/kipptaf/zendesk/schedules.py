from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.zendesk.assets import zendesk_user_sync

zendesk_user_sync_schedule = ScheduleDefinition(
    target=zendesk_user_sync,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    zendesk_user_sync_schedule,
]
