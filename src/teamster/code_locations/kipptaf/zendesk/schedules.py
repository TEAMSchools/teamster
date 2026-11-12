from dagster import ScheduleDefinition, define_asset_job, in_process_executor

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.zendesk.assets import zendesk_user_sync

zendesk_user_sync_schedule = ScheduleDefinition(
    name=f"{zendesk_user_sync.key.to_python_identifier()}_schedule",
    target=define_asset_job(
        name=f"{zendesk_user_sync.key.to_python_identifier()}_asset_job",
        selection=[zendesk_user_sync],
        executor_def=in_process_executor,
    ),
    cron_schedule="20 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    zendesk_user_sync_schedule,
]
