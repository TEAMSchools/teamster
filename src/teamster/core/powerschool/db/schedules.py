from dagster import ScheduleDefinition

from teamster.core.powerschool.db.jobs import powerschool_db_sync_std
from teamster.core.utils.variables import LOCAL_TIME_ZONE

powerschool_db_sync_std_schedule = ScheduleDefinition(
    job=powerschool_db_sync_std,
    cron_schedule="@hourly",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = ["powerschool_db_sync_std_schedule"]
