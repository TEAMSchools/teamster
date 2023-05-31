from dagster import build_schedule_from_partitioned_job

from .jobs import mclass_asset_job

mclass_asset_job_schedule = build_schedule_from_partitioned_job(
    job=mclass_asset_job, hour_of_day=0, minute_of_hour=0
)

__all__ = [
    mclass_asset_job_schedule,
]
