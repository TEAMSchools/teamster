from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.finalsite.assets import contacts
from teamster.libraries.finalsite.api.schedules import (
    build_finalsite_contacts_schedule,
)

finalsite_contacts_daily_asset_job_schedule = build_finalsite_contacts_schedule(
    code_location=CODE_LOCATION,
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[contacts],
    # 12:00 feeds the midday Focus import cycle, firing alongside the Focus dlt
    # pull rather than staggered behind it: they share no pool and neither gates
    # the other. The 12:45 delivery is a plain cron with a 45-minute time
    # budget, not a dependency -- an incremental pull uses ~1-2 min of it where
    # the full snapshot used ~5. 00:15 replaces the old 04:00: FRESH's 05:00
    # Tableau extract still reads a same-day pull, and the NJ consumers at 01:00
    # and 01:25 stop reading yesterday's. See #4715.
    #
    # Miami used to be the ONLY district on a midday tick, so the finalsite_api
    # pool (limit 1) was uncontended at 12:00. All four now share it. That is
    # still comfortably inside the budget: four INCREMENTAL pulls serialized is
    # ~6 min against the 45 min before the 12:45 delivery, where four full
    # snapshots would have been ~46 min and blown it.
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
    # one rebuild lands before the 12:45 delivery, which is a plain cron and
    # reports nothing when the model is stale. 10 min of lead against a ~3s
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
