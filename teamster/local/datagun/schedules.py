import os

from dagster import ScheduleDefinition

from teamster.local.datagun.jobs import (
    datagun_adp,
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

LOCAL_TIME_ZONE = os.getenv("LOCAL_TIME_ZONE")

datagun_gsheets = ScheduleDefinition(
    job=datagun_gsheets,
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_deanslist = ScheduleDefinition(
    job=datagun_deanslist,
    cron_schedule="25 1 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_illuminate = ScheduleDefinition(
    job=datagun_illuminate,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_clever = ScheduleDefinition(
    job=datagun_clever,
    cron_schedule="@hourly",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_razkids = ScheduleDefinition(
    job=datagun_razkids,
    cron_schedule="45 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_read180 = ScheduleDefinition(
    job=datagun_read180,
    cron_schedule="	15 3 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_gam = ScheduleDefinition(
    job=datagun_gam,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_littlesis = ScheduleDefinition(
    job=datagun_littlesis,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)


datagun_blissbook = ScheduleDefinition(
    job=datagun_blissbook,
    cron_schedule="10 5 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_coupa = ScheduleDefinition(
    job=datagun_coupa,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_egencia = ScheduleDefinition(
    job=datagun_egencia,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_adp = ScheduleDefinition(
    job=datagun_adp,
    cron_schedule="10 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_fpodms = ScheduleDefinition(
    job=datagun_fpodms,
    cron_schedule="40 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_njdoe = ScheduleDefinition(
    job=datagun_njdoe,
    cron_schedule="55 11 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_whetstone = ScheduleDefinition(
    job=datagun_whetstone,
    cron_schedule="55 3 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_idauto = ScheduleDefinition(
    job=datagun_idauto,
    cron_schedule="55 * * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

__all__ = [
    "datagun_deanslist",
    "datagun_illuminate",
    "datagun_gsheets",
    "datagun_clever",
    "datagun_razkids",
    "datagun_read180",
    "datagun_littlesis",
    "datagun_gam",
    "datagun_blissbook",
    "datagun_coupa",
    "datagun_egencia",
    "datagun_adp",
    "datagun_fpodms",
    "datagun_njdoe",
    "datagun_whetstone",
    "datagun_idauto",
]
