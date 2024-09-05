from dagster import (
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    define_asset_job,
    schedule,
)


def build_amplify_dibels_schedule(
    asset: AssetsDefinition, cron_schedule: str, execution_timezone: str
):
    job = define_asset_job(
        name=f"{asset.key.to_python_identifier()}_asset_job",
        selection=[asset],
        partitions_def=asset.partitions_def,
    )

    @schedule(
        name=f"{job.name}_schedule",
        job=job,
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
    )
    def _schedule(context: ScheduleEvaluationContext):
        partitions_def = _check.inst(
            obj=job.partitions_def,
            ttype=MultiPartitionsDefinition,
        )

        grade_partitions_def = partitions_def.get_partitions_def_for_dimension("grade")
        date_partitions_def = partitions_def.get_partitions_def_for_dimension("date")

        date_partition_key = _check.not_none(
            value=date_partitions_def.get_last_partition_key()
        )

        for grade in grade_partitions_def.get_partition_keys():
            yield RunRequest(
                partition_key=MultiPartitionKey(
                    {"date": date_partition_key, "grade": grade}
                )
            )

    return _schedule
