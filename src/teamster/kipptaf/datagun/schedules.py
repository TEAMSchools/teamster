from dagster import ScheduleDefinition

from .. import LOCAL_TIMEZONE
from .jobs import (
    adp_extract_asset_job,
    alchemer_extract_asset_job,
    blissbook_extract_asset_job,
    clever_extract_asset_job,
    coupa_extract_asset_job,
    deanslist_extract_asset_job,
    egencia_extract_asset_job,
    fpodms_extract_asset_job,
    gam_extract_asset_job,
    gsheet_extract_asset_job,
    idauto_extract_asset_job,
    illuminate_extract_asset_job,
    littlesis_extract_asset_job,
    njdoe_extract_asset_job,
    razkids_extract_asset_job,
    read180_extract_asset_job,
    whetstone_extract_asset_job,
)

gsheet_extract_assets_schedule = ScheduleDefinition(
    job=gsheet_extract_asset_job,
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_extract_assets_schedule = ScheduleDefinition(
    job=deanslist_extract_asset_job,
    cron_schedule="25 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

illuminate_extract_assets_schedule = ScheduleDefinition(
    job=illuminate_extract_asset_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

clever_extract_assets_schedule = ScheduleDefinition(
    job=clever_extract_asset_job,
    cron_schedule="@hourly",
    execution_timezone=LOCAL_TIMEZONE.name,
)

razkids_extract_assets_schedule = ScheduleDefinition(
    job=razkids_extract_asset_job,
    cron_schedule="45 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

read180_extract_assets_schedule = ScheduleDefinition(
    job=read180_extract_asset_job,
    cron_schedule="	15 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

gam_extract_assets_schedule = ScheduleDefinition(
    job=gam_extract_asset_job,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

littlesis_extract_assets_schedule = ScheduleDefinition(
    job=littlesis_extract_asset_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)


blissbook_extract_assets_schedule = ScheduleDefinition(
    job=blissbook_extract_asset_job,
    cron_schedule="10 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

coupa_extract_assets_schedule = ScheduleDefinition(
    job=coupa_extract_asset_job,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

egencia_extract_assets_schedule = ScheduleDefinition(
    job=egencia_extract_asset_job,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

adp_extract_assets_schedule = ScheduleDefinition(
    job=adp_extract_asset_job,
    cron_schedule="10 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

fpodms_extract_assets_schedule = ScheduleDefinition(
    job=fpodms_extract_asset_job,
    cron_schedule="40 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

njdoe_extract_assets_schedule = ScheduleDefinition(
    job=njdoe_extract_asset_job,
    cron_schedule="55 11 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

whetstone_extract_assets_schedule = ScheduleDefinition(
    job=whetstone_extract_asset_job,
    cron_schedule="55 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

idauto_extract_assets_schedule = ScheduleDefinition(
    job=idauto_extract_asset_job,
    cron_schedule="45 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

alchemer_extract_assets_schedule = ScheduleDefinition(
    job=alchemer_extract_asset_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

__all__ = [
    adp_extract_assets_schedule,
    alchemer_extract_assets_schedule,
    blissbook_extract_assets_schedule,
    clever_extract_assets_schedule,
    coupa_extract_assets_schedule,
    deanslist_extract_assets_schedule,
    egencia_extract_assets_schedule,
    fpodms_extract_assets_schedule,
    gam_extract_assets_schedule,
    gsheet_extract_assets_schedule,
    idauto_extract_assets_schedule,
    illuminate_extract_assets_schedule,
    littlesis_extract_assets_schedule,
    njdoe_extract_assets_schedule,
    razkids_extract_assets_schedule,
    read180_extract_assets_schedule,
    whetstone_extract_assets_schedule,
]
