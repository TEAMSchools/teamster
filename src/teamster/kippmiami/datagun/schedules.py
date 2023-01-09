from dagster import ScheduleDefinition
from teamster.local.datagun.jobs import datagun_ps_autocomm

from teamster.core.utils.variables import LOCAL_TIME_ZONE

datagun_ps_autocomm = ScheduleDefinition(
    job=datagun_ps_autocomm,
    cron_schedule="15 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = ["datagun_ps_autocomm"]
