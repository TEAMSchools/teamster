from dagster import ScheduleEvaluationContext, schedule
from dagster._core.definitions.partitioned_schedule import _get_schedule_evaluation_fn

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import school_ids
from .jobs import multi_partition_asset_job, static_partition_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=static_partition_asset_job,
)
def deanslist_static_partition_asset_job_schedule():
    for school_id in school_ids:
        yield static_partition_asset_job.run_request_for_partition(
            partition_key=school_id,
            run_key=(
                CODE_LOCATION + "_deanslist_static_partition_assets_job_" + school_id
            ),
        )


@schedule(
    cron_schedule=["0 0,14 * * *"],
    execution_timezone=LOCAL_TIMEZONE.name,
    job=multi_partition_asset_job,
)
def deanslist_multi_partition_asset_job_schedule(context: ScheduleEvaluationContext):
    schedule_evaluation_fn = _get_schedule_evaluation_fn(
        partitions_def=multi_partition_asset_job.partitions_def,
        job=multi_partition_asset_job,
    )

    schedule_evaluation_fn(context)


__all__ = [
    deanslist_static_partition_asset_job_schedule,
    deanslist_multi_partition_asset_job_schedule,
]
