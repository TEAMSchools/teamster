from dagster import (
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import workbook

job = define_asset_job(
    name=f"{CODE_LOCATION}_tableau_workbook_asset_job", selection=[workbook]
)

partitions_def: MultiPartitionsDefinition = workbook.partitions_def  # type: ignore

workbook_id_partition = partitions_def.get_partitions_def_for_dimension("workbook_id")
date_partition = partitions_def.get_partitions_def_for_dimension("date")

workbook_id_partition_keys = workbook_id_partition.get_partition_keys()
last_date_partition_key: str = date_partition.get_last_partition_key()  # type: ignore


@schedule(
    name=f"{job.name}_schedule",
    job=job,
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)
def tableau_workbook_asset_job_schedule(context: ScheduleEvaluationContext):
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


_all = [
    tableau_workbook_asset_job_schedule,
]
