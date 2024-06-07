from dagster import (
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    define_asset_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import workbook

job = define_asset_job(
    name=f"{CODE_LOCATION}_tableau_workbook_asset_job", selection=[workbook]
)


@schedule(
    name=f"{job.name}_schedule",
    job=job,
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)
def tableau_workbook_asset_job_schedule(context: ScheduleEvaluationContext):
    partitions_def = _check.inst(workbook.partitions_def, MultiPartitionsDefinition)

    workbook_id_partition = partitions_def.get_partitions_def_for_dimension(
        "workbook_id"
    )
    date_partition = partitions_def.get_partitions_def_for_dimension("date")

    workbook_id_partition_keys = workbook_id_partition.get_partition_keys()
    last_date_partition_key = _check.not_none(
        value=date_partition.get_last_partition_key()
    )

    for workbook_id in workbook_id_partition_keys:
        partition_key = MultiPartitionKey(
            {"workbook_id_partition": workbook_id, "date": last_date_partition_key}
        )

        yield RunRequest(
            run_key=f"{CODE_LOCATION}_{context._schedule_name}_{partition_key}",
            asset_selection=[workbook.key],
            partition_key=partition_key,
            tags={"tableau_pat_session_limit": "true"},
        )


schedules = [
    tableau_workbook_asset_job_schedule,
]
