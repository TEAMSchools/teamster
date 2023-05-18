from dagster import build_schedule_from_partitioned_job, schedule

from teamster.core.utils.variables import LOCAL_TIMEZONE

from .. import CODE_LOCATION
from .jobs import multi_partition_asset_job, static_partition_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=static_partition_asset_job,
)
def schoolmint_grow_static_partition_asset_job_schedule():
    for archived in ["t", "f"]:
        yield static_partition_asset_job.run_request_for_partition(
            partition_key=archived,
            run_key=(
                CODE_LOCATION
                + "_schoolmint_grow_static_partition_asset_job_"
                + archived
            ),
        )


multi_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=multi_partition_asset_job, hour_of_day=0, minute_of_hour=0
)

__all__ = [
    schoolmint_grow_static_partition_asset_job_schedule,
    multi_partition_asset_job_schedule,
]
