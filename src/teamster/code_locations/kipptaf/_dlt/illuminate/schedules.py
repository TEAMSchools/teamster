from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf._dlt.illuminate.jobs import (
    illuminate_dlt_daily_asset_job,
    illuminate_dlt_hourly_asset_job,
)

illuminate_dlt_daily_asset_job_schedule = ScheduleDefinition(
    job=illuminate_dlt_daily_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

illuminate_dlt_hourly_asset_job_schedule = ScheduleDefinition(
    job=illuminate_dlt_hourly_asset_job,
    cron_schedule="0 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    illuminate_dlt_daily_asset_job_schedule,
    illuminate_dlt_hourly_asset_job_schedule,
]
