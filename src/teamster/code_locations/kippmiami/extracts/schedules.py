from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

# Both schedules deliver the same four Focus import CSVs to the Focus SFTP
# `incoming/` folder. Enrollment ops run the Focus imports BY HAND, so a
# delivery is only useful if someone is on shift to consume it.
#
# NEITHER schedule is gated on its upstreams -- both are plain crons, so the gap
# between an upstream refresh and a delivery is a time budget, not a dependency.
#
# 13:15 is the staffed run. Leadership commits to stakeholders that a student
# entered in Finalsite by 12:00pm ET is usable in Focus by 2:00pm ET. Upstreams
# all run concurrently at 12:00 (the manual Finalsite SFTP push, the Finalsite
# contacts pull, the Focus dlt pull, and the dbt rebuild the
# automation-condition sensor fires off each). The binding term is the manual
# push: worst case ~11 min from push to rebuilt (5 min couchdrop sensor poll +
# 2m13s ingest + 3m34s dbt). Against the 75 min from noon to 13:15, the push
# and rebuild chain (worst case ~11 min) has ample room, and the 45 min from
# 13:15 to the 2pm commitment is slack for ops to run the import by hand. The
# 12:30 freshness check on #4736 stays actionable: a push prompted by it at
# 12:31 is rebuilt by ~12:42, well before this delivery.
#
# Pushing EARLY is not a safe fallback -- it misses anything entered between
# the push and the noon cutoff. Anything before ~12:11 puts the late bound
# before noon, contradicting the "entered by 12:00" promise outright.
#
# The name is kept as the job-name-derived default on purpose -- renaming
# mints a NEW Dagster+ schedule object and abandons this one's status and tick
# history.
focus_extract_assets_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__extracts__focus__asset_job_schedule",
    job=focus_extract_asset_job,
    cron_schedule="15 13 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

# 03:45 is the unstaffed run. It exists so the overnight state of Finalsite is
# already staged in Focus when ops start their shift, rather than waiting on the
# 13:15 delivery. Nobody is watching it, so it is deliberately NOT load-bearing
# for the 2pm commitment -- if it fails, 13:15 still satisfies the promise.
#
# The clock time is NOT tied to the 04:00 Focus dlt schedule, and must not be
# re-reasoned from it. That tier reloads only the count-only tables
# (`cursor_column: null`), which the import-once anti-join never reads. The
# tables it DOES read are `updated_at`-tracked, and
# `kippmiami__dlt__focus__intraday_sensor` keeps them within ~15 min of any
# change around the clock, so there is no stale-snapshot window to schedule
# around at 03:45 any more than at any other hour.
focus_extract_assets_overnight_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__extracts__focus__overnight_asset_job_schedule",
    job=focus_extract_asset_job,
    cron_schedule="45 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
    focus_extract_assets_overnight_schedule,
]
