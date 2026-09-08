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
    # step-pod scheduling wait, which only queues the run -- against 75 min before
    # the 13:15 delivery that is noise, and the 3600s max_runtime below absorbs it.
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

finalsite_enrollment_lifecycle_backstop_schedule = ScheduleDefinition(
    name=(
        f"{CODE_LOCATION}__finalsite__enrollment_lifecycle__backstop_asset_job_schedule"
    ),
    # A backstop for a race the eager automation condition cannot close on its
    # own. int_finalsite__enrollment_lifecycle joins the contacts API pull to the
    # manually-pushed SFTP status-report drop (see the comment above), and those
    # rebuild in separate concurrent runs. When they interleave, the model is
    # built from a status report older than the one on disk: enrollment_start_date
    # comes back null while assigned_school, from the same row, comes through. Its
    # eager any_deps_updated trigger is SINCE-wrapped, so the reset can consume
    # the trigger in the same tick that set it, and then nothing re-requests the
    # model -- observed 2026-08-11, stale for 75+ min across the delivery. #4834
    #
    # The eager condition still does all the normal work; this only guarantees
    # one rebuild lands before the 13:15 delivery, which is a plain cron and
    # reports nothing when the model is stale. 40 min of lead against a ~3s
    # build, and late enough that the worst-case SFTP chain (~12:26) has landed.
    #
    # A rebuild on a day when nothing was stale is accepted waste: one scan of a
    # small table, against silently dropping a student from the Focus import.
    cron_schedule="35 12 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{CODE_LOCATION}/finalsite/int_finalsite__enrollment_lifecycle"],
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
    finalsite_enrollment_lifecycle_backstop_schedule,
]
