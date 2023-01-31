from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippnewark.powerschool.db.jobs import nonpartition_assets_job

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=nonpartition_assets_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

__all__ = [powerschool_extract_assets_schedule]
