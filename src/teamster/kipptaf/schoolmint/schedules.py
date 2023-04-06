from dagster import RunRequest, build_schedule_from_partitioned_job, schedule

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .. import CODE_LOCATION
from . import jobs


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
    job=jobs.static_partition_asset_job,
)
def static_partition_assets_job_schedule():
    for archived in ["t", "f"]:
        yield RunRequest(
            run_key=(
                CODE_LOCATION
                + "_schoolmint_grow_static_partition_assets_job_"
                + archived
            ),
            partition_key=archived,
        )


multi_partition_assets_job_schedule = build_schedule_from_partitioned_job(
    job=jobs.multi_partition_asset_job, hour_of_day=0, minute_of_hour=0
)

__all__ = [
    static_partition_assets_job_schedule,
    multi_partition_assets_job_schedule,
]
