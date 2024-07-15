from typing import Generator

from dagster import (
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    define_asset_job,
    schedule,
)


def build_deanslist_job_schedule(
    code_location, partitions_type, selection, cron_schedule, execution_timezone
):
    job_name = f"{code_location}_deanslist_{partitions_type}_assets_job"

    job = define_asset_job(name=job_name, selection=selection)

    @schedule(
        name=f"{job_name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=job,
    )
    def _schedule(context: ScheduleEvaluationContext) -> Generator:
        if partitions_type == "static":
            school_partitions_def = _check.not_none(value=job.partitions_def)
            date_partition_key = ""
        else:
            partitions_def = _check.inst(
                obj=job.partitions_def, ttype=MultiPartitionsDefinition
            )

            school_partitions_def = partitions_def.get_partitions_def_for_dimension(
                "school"
            )
            date_partitions_def = partitions_def.get_partitions_def_for_dimension(
                "date"
            )

            date_partition_key = _check.not_none(
                value=date_partitions_def.get_last_partition_key()
            )

        for school_id in school_partitions_def.get_partition_keys():
            if partitions_type == "static":
                partition_key = school_id
            else:
                partition_key = MultiPartitionKey(
                    {"school": school_id, "date": date_partition_key}
                )

            yield RunRequest(
                run_key=f"{code_location}_{context._schedule_name}_{school_id}",
                partition_key=partition_key,
            )

    return _schedule
