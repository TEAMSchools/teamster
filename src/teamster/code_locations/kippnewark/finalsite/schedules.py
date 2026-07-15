from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{CODE_LOCATION}/finalsite/contacts"],
    # The finalsite_api pool (limit 1) serializes all four districts, so a run is
    # STARTED while it waits behind the others, which burns the run-timeout clock.
    # kippnewark's own pull (largest district, ~24k contacts, sequential ~1 req/s,
    # ~20 min) plus that queue wait can exceed the ~30 min default, so raise the
    # ceiling generously. See #4408.
    tags={MAX_RUNTIME_SECONDS_TAG: str(7200)},
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
