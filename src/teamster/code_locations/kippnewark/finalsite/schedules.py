from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{CODE_LOCATION}/finalsite/contacts"],
    # kippnewark (largest district, ~24k contacts) pulls sequentially at ~1 req/s
    # for ~20 min; adding GKE step-pod scheduling wait brushes the ~30 min default.
    # The finalsite_api pool (limit 1) serializes districts, but with run blocking
    # a waiting run stays QUEUED (not STARTED), so queue wait does not burn this
    # clock. 1h covers the pull plus scheduling with margin. See #4408.
    tags={MAX_RUNTIME_SECONDS_TAG: str(3600)},
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
