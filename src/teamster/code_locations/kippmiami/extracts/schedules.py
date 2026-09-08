from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

# Delivers the four Focus import CSVs to the Focus SFTP `incoming/` folder.
# Enrollment ops run the Focus imports BY HAND, so a delivery is only useful if
# someone is on shift to consume it -- hence two crons rather than a cadence.
#
# NOTHING GATES THIS ON ITS UPSTREAMS -- it is a plain cron, so the gap between
# an upstream refresh and a delivery is a time budget, not a dependency.
#
# 13:15 is the staffed run. Leadership commits to stakeholders that a student
# entered in Finalsite by 12:00pm ET is usable in Focus by 2:00pm ET. Upstreams
# all run concurrently at 12:00 (the manual Finalsite SFTP push, the Finalsite
# contacts pull, and the dbt rebuild the automation-condition sensor fires off
# each). The binding term is the manual push: worst case ~11 min from push to
# rebuilt (5 min couchdrop sensor poll + 2m13s ingest + 3m34s dbt). Against the
# 75 min from noon to 13:15 that chain has ample room, and the 45 min from 13:15
# to the 2pm commitment is slack for ops to run the import by hand. The 12:30
# freshness check on #4736 stays actionable: a push prompted by it at 12:31 is
# rebuilt by ~12:42, well before this delivery.
#
# Pushing EARLY is not a safe fallback -- it misses anything entered between
# the push and the noon cutoff. Anything before ~12:11 puts the late bound
# before noon, contradicting the "entered by 12:00" promise outright.
#
# 03:45 is the unstaffed run, so the overnight state of Finalsite is already
# staged in Focus when ops start their shift rather than waiting on 13:15. It is
# deliberately NOT load-bearing for the 2pm commitment -- if it fails, 13:15
# still satisfies the promise.
#
# That clock time is NOT tied to the 04:00 Focus dlt schedule and must not be
# re-reasoned from it. That tier reloads only the count-only tables
# (`cursor_column: null`), which the import-once anti-join never reads. The
# tables it DOES read are `updated_at`-tracked, and
# `kippmiami__dlt__focus__intraday_sensor` keeps them within ~15 min of any
# change around the clock, so there is no stale-snapshot window to schedule
# around at 03:45 any more than at any other hour.
#
# ONE ScheduleDefinition with two crons, not two definitions: a second schedule
# object would have to be enabled separately in Dagster+ and would carry its own
# status and tick history for no benefit, since both crons target the same job
# with the same config. The name is pinned to the job-name-derived default on
# purpose -- renaming (or renaming the job) mints a NEW Dagster+ schedule object
# and abandons this one's status and tick history.
focus_extract_assets_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__extracts__focus__asset_job_schedule",
    job=focus_extract_asset_job,
    cron_schedule=["15 13 * * *", "45 3 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
]
