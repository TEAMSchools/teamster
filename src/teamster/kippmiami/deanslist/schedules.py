from dagster import MultiPartitionKey, MultiPartitionsDefinition, schedule

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .jobs import multi_partition_asset_job, static_partition_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=static_partition_asset_job,
)
def deanslist_static_partition_asset_job_schedule():
    for school_id in static_partition_asset_job.partitions_def.get_partition_keys():
        yield static_partition_asset_job.run_request_for_partition(
            partition_key=school_id,
            run_key=f"{CODE_LOCATION}_deanslist_static_partition_asset_job_{school_id}",
        )


@schedule(
    cron_schedule="0 0,15 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=multi_partition_asset_job,
)
def multi_partition_asset_job_schedule():
    multi_partitions_def: MultiPartitionsDefinition = (
        multi_partition_asset_job.partitions_def
    )

    date_partition = multi_partitions_def.get_partitions_def_for_dimension("date")
    school_partition = multi_partitions_def.get_partitions_def_for_dimension("school")

    last_date_partition_key = date_partition.get_last_partition_key()

    for school in school_partition.get_partition_keys():
        partition_key = MultiPartitionKey(
            {"school": school, "date": last_date_partition_key}
        )
        yield multi_partition_asset_job.run_request_for_partition(
            partition_key=partition_key,
            run_key=(
                f"{CODE_LOCATION}_deanslist_multi_partition_asset_job_{partition_key}"
            ),
        )


__all__ = [
    deanslist_static_partition_asset_job_schedule,
    multi_partition_asset_job_schedule,
]
