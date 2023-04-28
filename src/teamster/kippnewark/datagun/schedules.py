from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .jobs import nps_extract_asset_job, powerschool_extract_asset_job

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

nps_extract_assets_schedule = ScheduleDefinition(
    job=nps_extract_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

__all__ = [
    powerschool_extract_assets_schedule,
    nps_extract_assets_schedule,
]
