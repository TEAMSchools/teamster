from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{CODE_LOCATION}/finalsite/contacts"],
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
