from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.smartrecruiters.assets import assets

smartrecruiters_report_assets_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__smartrecruiters__assets_schedule",
    target=assets,
    # ahead of the recruitment_dashboard refresh (exposures/tableau.yml); the
    # afternoon tick stays off :00, when run pods wait longest for nodes
    cron_schedule=["0 6 * * *", "15 13 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
    # max_runtime counts step-pod scheduling too; the 6am report queues PENDING
    # in SmartRecruiters for minutes before it runs
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 20)},
)

schedules = [
    smartrecruiters_report_assets_schedule,
]
