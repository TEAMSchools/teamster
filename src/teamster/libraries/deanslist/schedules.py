from typing import Generator

from dagster import (
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    StaticPartitionsDefinition,
    _check,
    define_asset_job,
    schedule,
)


def build_deanslist_job_schedule(
    job_name: str,
    selection,
    partitions_def: StaticPartitionsDefinition | MultiPartitionsDefinition,
    cron_schedule: str,
    execution_timezone,
):
    job = define_asset_job(
        name=job_name, selection=selection, partitions_def=partitions_def
    )

    @schedule(
        name=f"{job.name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=job,
    )
    def _schedule(context: ScheduleEvaluationContext) -> Generator:
        partition_keys = []

        if isinstance(partitions_def, StaticPartitionsDefinition):
            partition_keys = partitions_def.get_partition_keys()
        elif isinstance(partitions_def, MultiPartitionsDefinition):
            school_partitions_def = partitions_def.get_partitions_def_for_dimension(
                "school"
            )
            date_partitions_def = partitions_def.get_partitions_def_for_dimension(
                "date"
            )

            school_partition_keys = school_partitions_def.get_partition_keys()
            date_partition_key = _check.not_none(
                value=date_partitions_def.get_last_partition_key()
            )

            partition_keys = [
                MultiPartitionKey({"school": school_id, "date": date_partition_key})
                for school_id in school_partition_keys
            ]

        for partition_key in partition_keys:
            yield RunRequest(
                run_key=f"{context._schedule_name}_{partition_key}",
                partition_key=partition_key,
            )

    return _schedule
