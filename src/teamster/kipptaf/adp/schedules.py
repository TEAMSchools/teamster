from dagster import build_schedule_from_partitioned_job

from .jobs import daily_partition_asset_job

daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=daily_partition_asset_job, hour_of_day=0, minute_of_hour=0
)


__all__ = [
    daily_partition_asset_job_schedule,
]
