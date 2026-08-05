from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    # Delivers the four Focus import CSVs to the Focus SFTP `incoming/` folder.
    # Enrollment ops run the Focus imports BY HAND, and leadership commits to
    # stakeholders that a student entered in Finalsite by 12:00pm ET is usable in
    # Focus by 2:00pm ET -- so this lands at 12:45pm, leaving ops a 75-minute
    # window. Upstreams that must finish first: the manual Finalsite SFTP push
    # (~12:00, ingested within 10 min by the couchdrop sensor), the midday
    # Finalsite contacts pull (12:10), the midday Focus dlt pull (12:25), and the
    # dbt rebuild the automation-condition sensor fires off those (~3.5 min).
    cron_schedule="45 12 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
]
