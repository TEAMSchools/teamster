from dagster import ScheduleDefinition, define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.smartrecruiters.assets import assets

smartrecruiters_report_assets_schedule = ScheduleDefinition(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_smartrecruiters_report_asset_job", selection=assets
    ),
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    smartrecruiters_report_assets_schedule,
]
