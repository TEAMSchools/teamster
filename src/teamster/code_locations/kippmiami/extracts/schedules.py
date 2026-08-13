from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
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
# 2m13s ingest + 3m34s dbt). Against the 75 min from 13:15 to the 2pm
# commitment, that leaves the 12:00-12:15 push window ample margin and keeps the
# 12:30 freshness check on #4736 actionable -- a push prompted by it at 12:31 is
# rebuilt by ~12:42 and still makes this delivery.
#
# Delivering EARLIER is not a safe fallback: it misses anything entered between
# the push and the noon cutoff, and anything before ~12:11 puts the late bound
# before noon, contradicting the "entered by 12:00" promise outright.
focus_extract_assets_schedule = ScheduleDefinition(
    name="focus_extract_assets_schedule",
    job=focus_extract_asset_job,
    cron_schedule="15 13 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

# 03:45 is the unstaffed run. It exists so the overnight state of Finalsite is
# already staged in Focus when ops start their shift, rather than waiting on the
# 13:15 delivery. Nobody is watching it, so it is deliberately NOT load-bearing
# for the 2pm commitment -- if it fails, 13:15 still satisfies the promise.
focus_extract_assets_overnight_schedule = ScheduleDefinition(
    name="focus_extract_assets_overnight_schedule",
    job=focus_extract_asset_job,
    cron_schedule="45 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
    focus_extract_assets_overnight_schedule,
]
