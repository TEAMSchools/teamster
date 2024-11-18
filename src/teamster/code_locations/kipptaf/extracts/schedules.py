from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.extracts.jobs import (
    clever_extract_asset_job,
    coupa_extract_asset_job,
    deanslist_annual_extract_asset_job,
    deanslist_continuous_extract_asset_job,
    egencia_extract_asset_job,
    idauto_extract_asset_job,
    illuminate_extract_asset_job,
    littlesis_extract_asset_job,
)

clever_extract_assets_schedule = ScheduleDefinition(
    job=clever_extract_asset_job,
    cron_schedule="@hourly",
    execution_timezone=str(LOCAL_TIMEZONE),
)

coupa_extract_assets_schedule = ScheduleDefinition(
    job=coupa_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

deanslist_annual_extract_asset_job_schedule = ScheduleDefinition(
    job=deanslist_annual_extract_asset_job,
    cron_schedule="25 1 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

deanslist_continuous_extract_asset_job_schedule = ScheduleDefinition(
    job=deanslist_continuous_extract_asset_job,
    cron_schedule="25 1 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

egencia_extract_assets_schedule = ScheduleDefinition(
    job=egencia_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

idauto_extract_assets_schedule = ScheduleDefinition(
    job=idauto_extract_asset_job,
    cron_schedule="15 1 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

illuminate_extract_assets_schedule = ScheduleDefinition(
    job=illuminate_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

littlesis_extract_assets_schedule = ScheduleDefinition(
    job=littlesis_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    clever_extract_assets_schedule,
    coupa_extract_assets_schedule,
    deanslist_annual_extract_asset_job_schedule,
    deanslist_continuous_extract_asset_job_schedule,
    egencia_extract_assets_schedule,
    idauto_extract_assets_schedule,
    illuminate_extract_assets_schedule,
    littlesis_extract_assets_schedule,
]
