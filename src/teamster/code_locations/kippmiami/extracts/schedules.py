from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    # Delivers the four Focus import CSVs to the Focus SFTP `incoming/` folder.
    # Enrollment ops run the Focus imports BY HAND, and leadership commits to
    # stakeholders that a student entered in Finalsite by 12:00pm ET is usable in
    # Focus by 2:00pm ET -- so this lands at 12:45pm, leaving ops a 75-minute
    # window. Upstreams, all of which run concurrently at 12:00: the manual
    # Finalsite SFTP push (ingested within 10 min by the couchdrop sensor), the
    # Finalsite contacts pull, the Focus dlt pull, and the dbt rebuild the
    # automation-condition sensor fires off each of those (~3.5 min).
    #
    # NOTHING GATES THIS ON THOSE UPSTREAMS -- it is a plain cron, so the gap is a
    # time budget, not a dependency. Measured need is 4-7 min after a schedule
    # fires, or ~16 min from a manual SFTP push in the worst case (10 min sensor
    # poll + 2 min ingest + 3.5 min dbt), plus up to 9 min of top-of-hour GKE
    # step-pod scheduling wait, which queues rather than fails. The budget is 45
    # min. Moving this earlier, or an upstream later, spends that margin; a push
    # after ~12:29 is not guaranteed to make this delivery.
    cron_schedule="45 12 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
]
