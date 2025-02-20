from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE

key_prefix = f"{CODE_LOCATION}/dlt/zendesk/support"

zendesk_dlt_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__zendesk__asset_job",
    target=[
        f"{key_prefix}/groups",
        f"{key_prefix}/ticket_events",
        f"{key_prefix}/ticket_metrics",
        f"{key_prefix}/tickets",
        f"{key_prefix}/users",
    ],
    cron_schedule="0 5 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    zendesk_dlt_asset_job_schedule,
]
