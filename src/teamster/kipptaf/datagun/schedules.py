from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kipptaf.datagun.jobs import (
    datagun_adp,
    datagun_alchemer,
    datagun_blissbook,
    datagun_clever,
    datagun_coupa,
    datagun_deanslist,
    datagun_egencia,
    datagun_fpodms,
    datagun_gam,
    datagun_gsheets,
    datagun_idauto,
    datagun_illuminate,
    datagun_littlesis,
    datagun_njdoe,
    datagun_razkids,
    datagun_read180,
    datagun_whetstone,
)

datagun_gsheets_schedule = ScheduleDefinition(
    job=datagun_gsheets,
    cron_schedule="0 6 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_deanslist_schedule = ScheduleDefinition(
    job=datagun_deanslist,
    cron_schedule="25 1 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_illuminate_schedule = ScheduleDefinition(
    job=datagun_illuminate,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_clever_schedule = ScheduleDefinition(
    job=datagun_clever,
    cron_schedule="@hourly",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_razkids_schedule = ScheduleDefinition(
    job=datagun_razkids,
    cron_schedule="45 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_read180_schedule = ScheduleDefinition(
    job=datagun_read180,
    cron_schedule="	15 3 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_gam_schedule = ScheduleDefinition(
    job=datagun_gam,
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_littlesis_schedule = ScheduleDefinition(
    job=datagun_littlesis,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)


datagun_blissbook_schedule = ScheduleDefinition(
    job=datagun_blissbook,
    cron_schedule="10 5 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_coupa_schedule = ScheduleDefinition(
    job=datagun_coupa,
    cron_schedule="20 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_egencia_schedule = ScheduleDefinition(
    job=datagun_egencia,
    cron_schedule="20 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_adp_schedule = ScheduleDefinition(
    job=datagun_adp,
    cron_schedule="10 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_fpodms_schedule = ScheduleDefinition(
    job=datagun_fpodms,
    cron_schedule="40 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_njdoe_schedule = ScheduleDefinition(
    job=datagun_njdoe,
    cron_schedule="55 11 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_whetstone_schedule = ScheduleDefinition(
    job=datagun_whetstone,
    cron_schedule="55 3 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_idauto_schedule = ScheduleDefinition(
    job=datagun_idauto,
    cron_schedule="45 0 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_alchemer_schedule = ScheduleDefinition(
    job=datagun_alchemer,
    cron_schedule="30 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = [
    "datagun_deanslist_schedule",
    "datagun_illuminate_schedule",
    "datagun_gsheets_schedule",
    "datagun_clever_schedule",
    "datagun_razkids_schedule",
    "datagun_read180_schedule",
    "datagun_littlesis_schedule",
    "datagun_gam_schedule",
    "datagun_blissbook_schedule",
    "datagun_coupa_schedule",
    "datagun_egencia_schedule",
    "datagun_adp_schedule",
    "datagun_fpodms_schedule",
    "datagun_njdoe_schedule",
    "datagun_whetstone_schedule",
    "datagun_idauto_schedule",
    "datagun_alchemer_schedule",
]
