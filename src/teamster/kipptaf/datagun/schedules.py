from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kipptaf.datagun import jobs

gsheet_extract_assets_schedule = ScheduleDefinition(
    job=jobs.gsheet_extract_assets_job,
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

deanslist_extract_assets_schedule = ScheduleDefinition(
    job=jobs.deanslist_extract_assets_job,
    cron_schedule="25 1 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

illuminate_extract_assets_schedule = ScheduleDefinition(
    job=jobs.illuminate_extract_assets_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

clever_extract_assets_schedule = ScheduleDefinition(
    job=jobs.clever_extract_assets_job,
    cron_schedule="@hourly",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

razkids_extract_assets_schedule = ScheduleDefinition(
    job=jobs.razkids_extract_assets_job,
    cron_schedule="45 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

read180_extract_assets_schedule = ScheduleDefinition(
    job=jobs.read180_extract_assets_job,
    cron_schedule="	15 3 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

gam_extract_assets_schedule = ScheduleDefinition(
    job=jobs.gam_extract_assets_job,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

littlesis_extract_assets_schedule = ScheduleDefinition(
    job=jobs.littlesis_extract_assets_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)


blissbook_extract_assets_schedule = ScheduleDefinition(
    job=jobs.blissbook_extract_assets_job,
    cron_schedule="10 5 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

coupa_extract_assets_schedule = ScheduleDefinition(
    job=jobs.coupa_extract_assets_job,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

egencia_extract_assets_schedule = ScheduleDefinition(
    job=jobs.egencia_extract_assets_job,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

adp_extract_assets_schedule = ScheduleDefinition(
    job=jobs.adp_extract_assets_job,
    cron_schedule="10 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

fpodms_extract_assets_schedule = ScheduleDefinition(
    job=jobs.fpodms_extract_assets_job,
    cron_schedule="40 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

njdoe_extract_assets_schedule = ScheduleDefinition(
    job=jobs.njdoe_extract_assets_job,
    cron_schedule="55 11 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

whetstone_extract_assets_schedule = ScheduleDefinition(
    job=jobs.whetstone_extract_assets_job,
    cron_schedule="55 3 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

idauto_extract_assets_schedule = ScheduleDefinition(
    job=jobs.idauto_extract_assets_job,
    cron_schedule="45 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

alchemer_extract_assets_schedule = ScheduleDefinition(
    job=jobs.alchemer_extract_assets_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
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
