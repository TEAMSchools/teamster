from dagster import schedule

from .. import CODE_LOCATION, CURRENT_FISCAL_YEAR, LOCAL_TIMEZONE
from .jobs import mclass_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    name=f"{CODE_LOCATION}_{mclass_asset_job.name}",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=mclass_asset_job,
)
def mclass_asset_job_schedule():
    partition_key = CURRENT_FISCAL_YEAR.start.to_date_string
    yield mclass_asset_job.run_request_for_partition(
        partition_key=partition_key,
        run_key=f"{CODE_LOCATION}_{mclass_asset_job.name}_{partition_key}",
    )


__all__ = [
    mclass_asset_job_schedule,
]
