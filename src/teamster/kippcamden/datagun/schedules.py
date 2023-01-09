from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippcamden.datagun.jobs import datagun_cpn, datagun_ps_autocomm

datagun_ps_autocomm = ScheduleDefinition(
    job=datagun_ps_autocomm,
    cron_schedule="15 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

datagun_cpn = ScheduleDefinition(
    job=datagun_cpn,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = [
    "datagun_ps_autocomm",
    "datagun_cpn",
]
