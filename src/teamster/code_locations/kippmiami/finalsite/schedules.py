from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    # "daily" is now twice a day. The name is kept as-is on purpose -- renaming
    # mints a NEW Dagster+ schedule object and abandons this one's status and
    # tick history.
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    # 04:00 stays for the overnight refresh every other Finalsite consumer reads.
    # 12:00 feeds the midday Focus import cycle, firing alongside the Focus dlt
    # pull rather than staggered behind it: they share no pool and neither gates
    # the other (this API pull and the manually-pushed SFTP drop feed opposite
    # sides of int_finalsite__enrollment_lifecycle; the dlt pull feeds the
    # import-once anti-join). Top-of-hour GKE Autopilot fan-out can add 3-9 min of
    # step-pod scheduling wait, which only queues the run -- against 30 min before
    # the 12:30 delivery that is noise, and the 3600s max_runtime below absorbs it.
    #
    # Miami is the only district on a midday tick, so the finalsite_api pool
    # (limit 1) is uncontended then -- at 04:00 the four districts serialize and
    # Miami has waited up to 46 minutes for a slot.
    cron_schedule=["0 4 * * *", "0 12 * * *"],
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
