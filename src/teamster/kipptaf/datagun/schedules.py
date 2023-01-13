from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kipptaf.datagun.jobs import (
    adp_extract_assets_job,
    alchemer_extract_assets_job,
    blissbook_extract_assets_job,
    clever_extract_assets_job,
    coupa_extract_assets_job,
    deanslist_extract_assets_job,
    egencia_extract_assets_job,
    fpodms_extract_assets_job,
    gam_extract_assets_job,
    gsheet_extract_assets_job,
    idauto_extract_assets_job,
    illuminate_extract_assets_job,
    littlesis_extract_assets_job,
    njdoe_extract_assets_job,
    razkids_extract_assets_job,
    read180_extract_assets_job,
    whetstone_extract_assets_job,
)

gsheet_extract_assets_schedule = ScheduleDefinition(
    job=gsheet_extract_assets_job,
    cron_schedule="0 6 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

deanslist_extract_assets_schedule = ScheduleDefinition(
    job=deanslist_extract_assets_job,
    cron_schedule="25 1 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

illuminate_extract_assets_schedule = ScheduleDefinition(
    job=illuminate_extract_assets_job,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

clever_extract_assets_schedule = ScheduleDefinition(
    job=clever_extract_assets_job,
    cron_schedule="@hourly",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

razkids_extract_assets_schedule = ScheduleDefinition(
    job=razkids_extract_assets_job,
    cron_schedule="45 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

read180_extract_assets_schedule = ScheduleDefinition(
    job=read180_extract_assets_job,
    cron_schedule="	15 3 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

gam_extract_assets_schedule = ScheduleDefinition(
    job=gam_extract_assets_job,
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

littlesis_extract_assets_schedule = ScheduleDefinition(
    job=littlesis_extract_assets_job,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)


blissbook_extract_assets_schedule = ScheduleDefinition(
    job=blissbook_extract_assets_job,
    cron_schedule="10 5 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

coupa_extract_assets_schedule = ScheduleDefinition(
    job=coupa_extract_assets_job,
    cron_schedule="20 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

egencia_extract_assets_schedule = ScheduleDefinition(
    job=egencia_extract_assets_job,
    cron_schedule="20 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

adp_extract_assets_schedule = ScheduleDefinition(
    job=adp_extract_assets_job,
    cron_schedule="10 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

fpodms_extract_assets_schedule = ScheduleDefinition(
    job=fpodms_extract_assets_job,
    cron_schedule="40 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

njdoe_extract_assets_schedule = ScheduleDefinition(
    job=njdoe_extract_assets_job,
    cron_schedule="55 11 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

whetstone_extract_assets_schedule = ScheduleDefinition(
    job=whetstone_extract_assets_job,
    cron_schedule="55 3 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

idauto_extract_assets_schedule = ScheduleDefinition(
    job=idauto_extract_assets_job,
    cron_schedule="45 0 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

alchemer_extract_assets_schedule = ScheduleDefinition(
    job=alchemer_extract_assets_job,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)
