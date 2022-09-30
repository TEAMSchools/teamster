import os

from dagster import ScheduleDefinition

from teamster.local.datagun.jobs import datagun_nps, datagun_ps_autocomm

LOCAL_TIME_ZONE = os.getenv("LOCAL_TIME_ZONE")

datagun_ps_autocomm = ScheduleDefinition(
    name="datagun_powerschool",
    job=datagun_ps_autocomm,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

datagun_nps = ScheduleDefinition(
    name="nps_datagun",
    job=datagun_nps,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
)

__all__ = [
    "datagun_ps_autocomm",
    "datagun_nps",
]
