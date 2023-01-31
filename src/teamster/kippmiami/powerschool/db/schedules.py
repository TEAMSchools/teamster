from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippmiami.powerschool.db.jobs import nonpartition_assets_job

powerschool_nonpartition_assets_job_schedule = ScheduleDefinition(
    name="powerschool_nonpartition_assets_job_schedule",
    job=nonpartition_assets_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

__all__ = [powerschool_nonpartition_assets_job_schedule]
