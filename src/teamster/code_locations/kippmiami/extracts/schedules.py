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

# 04:30 is the unstaffed run. It must fire AFTER the 04:00 Focus dlt pull has
# landed in stg_focus -- the import-once anti-join reads that snapshot, and
# delivering against a stale one re-sends records ops already imported by
# hand, duplicating them in Focus. Nobody is watching this run, so it is
# deliberately NOT load-bearing for the 2pm commitment -- if it fails, 13:15
# still satisfies the promise.
focus_extract_assets_overnight_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__extracts__focus__overnight_asset_job_schedule",
    job=focus_extract_asset_job,
    cron_schedule="30 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
    focus_extract_assets_overnight_schedule,
]
