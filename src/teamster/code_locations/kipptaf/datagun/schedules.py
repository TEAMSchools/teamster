from dagster import MAX_RUNTIME_SECONDS_TAG, ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.datagun.jobs import (
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
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 8)},
)

coupa_extract_assets_schedule = ScheduleDefinition(
    job=coupa_extract_asset_job,
    cron_schedule="30 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_annual_extract_asset_job_schedule = ScheduleDefinition(
    job=deanslist_annual_extract_asset_job,
    cron_schedule="25 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 14)},
)

deanslist_continuous_extract_asset_job_schedule = ScheduleDefinition(
    job=deanslist_continuous_extract_asset_job,
    cron_schedule="25 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 14)},
)

egencia_extract_assets_schedule = ScheduleDefinition(
    job=egencia_extract_asset_job,
    cron_schedule="30 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

idauto_extract_assets_schedule = ScheduleDefinition(
    job=idauto_extract_asset_job,
    cron_schedule="0 4 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    tags={MAX_RUNTIME_SECONDS_TAG: str(60 * 5)},
)

illuminate_extract_assets_schedule = ScheduleDefinition(
    job=illuminate_extract_asset_job,
    cron_schedule="30 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

littlesis_extract_assets_schedule = ScheduleDefinition(
    job=littlesis_extract_asset_job,
    cron_schedule="30 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
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
