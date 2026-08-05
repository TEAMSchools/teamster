from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    # Delivers the four Focus import CSVs to the Focus SFTP `incoming/` folder.
    # Enrollment ops run the Focus imports BY HAND, and leadership commits to
    # stakeholders that a student entered in Finalsite by 12:00pm ET is usable in
    # Focus by 2:00pm ET. The imports are near-instant, so the 75 min between this
    # delivery and 2pm is slack rather than a window being consumed.
    #
    # Upstreams all run concurrently at 12:00 (nothing about them is sequential):
    # the manual Finalsite SFTP push, the Finalsite contacts pull, the Focus dlt
    # pull, and the dbt rebuild the automation-condition sensor fires off each.
    #
    # NOTHING GATES THIS ON THOSE UPSTREAMS -- it is a plain cron, so the gap is a
    # time budget, not a dependency. The binding term is the manual SFTP push, not
    # any ordering between Finalsite and Focus: worst case ~11 min from push to
    # rebuilt (5 min couchdrop sensor poll + 2m13s ingest + 3m34s dbt); the
    # scheduled pulls need only 4-7 min. Against 45 min of budget that leaves the
    # 12:00-12:15 push window ~19 min of margin, and lets the 12:30 freshness check
    # on #4736 be actionable: a push prompted by it at 12:31 is rebuilt by ~12:42
    # and still makes this delivery.
    #
    # Pushing EARLY is not a safe fallback -- it misses anything entered between
    # the push and the noon cutoff. Anything before ~12:11 puts the late bound
    # before noon, contradicting the "entered by 12:00" promise outright.
    cron_schedule="45 12 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
]
