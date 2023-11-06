from dagster import (
    AssetKey,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    build_schedule_from_partitioned_job,
    schedule,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .jobs import multi_partition_asset_job, static_partition_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=static_partition_asset_job,
)
def deanslist_static_partition_asset_job_schedule():
    for school_id in static_partition_asset_job.partitions_def.get_partition_keys():
        yield RunRequest(
            run_key=f"{CODE_LOCATION}_deanslist_static_partition_{school_id}",
            partition_key=school_id,
        )


deanslist_multi_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=multi_partition_asset_job, hour_of_day=0, minute_of_hour=0
)


@schedule(
    cron_schedule="0 14 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=multi_partition_asset_job,
)
def deanslist_comm_log_midday_job_schedule():
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

        yield RunRequest(
            run_key=(f"{CODE_LOCATION}_deanslist_comm_log_midday_{partition_key}"),
            asset_selection=[AssetKey([CODE_LOCATION, "deanslist", "comm_log"])],
            partition_key=partition_key,
        )


__all__ = [
    deanslist_comm_log_midday_job_schedule,
    deanslist_multi_partition_asset_job_schedule,
    deanslist_static_partition_asset_job_schedule,
]
