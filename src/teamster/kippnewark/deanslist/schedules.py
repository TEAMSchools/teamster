from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippnewark.deanslist import jobs

deanslist_school_partition_assets_job_schedule = ScheduleDefinition(
    job=jobs.deanslist_school_partition_assets_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

deanslist_multi_partition_assets_job_schedule = ScheduleDefinition(
    job=jobs.deanslist_multi_partition_assets_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

__all__ = [
    deanslist_school_partition_assets_job_schedule,
    deanslist_multi_partition_assets_job_schedule,
]
