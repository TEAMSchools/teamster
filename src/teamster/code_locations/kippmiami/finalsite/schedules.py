from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    # 04:00 stays for the overnight refresh every other Finalsite consumer reads.
    # 12:10 feeds the midday Focus import cycle: it runs after enrollment ops push
    # the Finalsite SFTP export at 12:00, and int_finalsite__enrollment_lifecycle
    # needs BOTH this API pull and that SFTP drop before the rpt_focus__* extracts
    # mean anything. Miami is the only district on a midday tick, so the
    # finalsite_api pool is uncontended then -- at 04:00 the four districts
    # serialize and Miami has waited up to 46 minutes for a slot.
    cron_schedule=["0 4 * * *", "10 12 * * *"],
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
