from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.local.powerschool.jobs.db import powerschool_db_sync_ext

powerschool_db_sync_ext_schedule = ScheduleDefinition(
    job=powerschool_db_sync_ext,
    cron_schedule="@hourly",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = ["powerschool_db_sync_ext_schedule"]
