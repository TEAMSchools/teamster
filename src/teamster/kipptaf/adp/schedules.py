from dagster import build_schedule_from_partitioned_job

from .jobs import daily_partition_asset_jobs

daily_partition_asset_job_schedules = [
    build_schedule_from_partitioned_job(job=job, hour_of_day=0, minute_of_hour=0)
    for job in daily_partition_asset_jobs
]

__all__ = [
    *daily_partition_asset_job_schedules,
]
