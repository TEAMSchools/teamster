from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{CODE_LOCATION}/finalsite/contacts"],
    # Covers a full sequential pull plus GKE step-pod scheduling wait. The
    # finalsite_api pool (limit 1) serializes districts; a waiting run stays
    # QUEUED, so queue wait does not burn this clock. See #4408.
    tags={MAX_RUNTIME_SECONDS_TAG: str(3600)},
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
