from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    schedule,
)

from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition


def build_deanslist_static_partition_asset_job_schedule(
    code_location, cron_schedule, execution_timezone, job
):
    schedule_name = f"{code_location}_deanslist_static_partition_asset_job_schedule"
    partition_keys = job.partitions_def.get_partition_keys()

    @schedule(
        name=schedule_name,
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=job,
    )
    def _schedule(context: ScheduleEvaluationContext):
        for school_id in partition_keys:
            yield RunRequest(
                run_key=f"{code_location}_{schedule_name}_{school_id}",
                partition_key=school_id,
            )

    return _schedule


def build_deanslist_multi_partition_asset_job_schedule(
    code_location,
    cron_schedule,
    execution_timezone,
    job,
    asset_selection=None,
    schedule_name=None,
):
    partitions_def: MultiPartitionsDefinition = job.partitions_def

    date_partition = partitions_def.get_partitions_def_for_dimension("date")
    school_partition = partitions_def.get_partitions_def_for_dimension("school")

    last_date_partition_key = _check.not_none(
        value=date_partition.get_last_partition_key()
    )

    if schedule_name is None:
        if isinstance(date_partition, MonthlyPartitionsDefinition):
            date_partition_type = "monthly"
        elif isinstance(date_partition, FiscalYearPartitionsDefinition):
            date_partition_type = "fiscal"
        else:
            date_partition_type = ""

        schedule_name = (
            f"{code_location}_deanslist_multi_partition_{date_partition_type}"
            "_asset_job_schedule"
        )

    @schedule(
        name=schedule_name,
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=job,
    )
    def _schedule(context: ScheduleEvaluationContext):
        for school in school_partition.get_partition_keys():
            partition_key = MultiPartitionKey(
                {"school": school, "date": last_date_partition_key}
            )

            yield RunRequest(
                run_key=f"{code_location}_{schedule_name}_{partition_key}",
                asset_selection=asset_selection,
                partition_key=partition_key,
            )

    return _schedule
