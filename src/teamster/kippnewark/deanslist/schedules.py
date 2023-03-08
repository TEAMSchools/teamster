from dagster import schedule

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .. import CODE_LOCATION
from . import assets, jobs


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
    job=jobs.deanslist_static_partition_assets_job,
)
def deanslist_static_partition_assets_job_schedule():
    for school_id in assets.school_ids:
        run_request = (
            jobs.deanslist_static_partition_assets_job.run_request_for_partition(
                partition_key=school_id,
                run_key=(
                    CODE_LOCATION
                    + "_deanslist_static_partition_assets_job_"
                    + school_id
                ),
            )
        )

        yield run_request


__all__ = [
    deanslist_static_partition_assets_job_schedule,
]
