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

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import workbook

job = define_asset_job(
    name=f"{CODE_LOCATION}_tableau_workbook_asset_job", selection=[workbook]
)

partitions_def = _check.inst(workbook.partitions_def, MultiPartitionsDefinition)

workbook_id_partition = partitions_def.get_partitions_def_for_dimension("workbook_id")

DATE_PARTITION = partitions_def.get_partitions_def_for_dimension("date")

WORKBOOK_ID_PARTITION_KEYS = workbook_id_partition.get_partition_keys()


@schedule(
    name=f"{job.name}_schedule",
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=job,
)
def tableau_workbook_asset_job_schedule(
    context: ScheduleEvaluationContext,
) -> Generator:
    last_date_partition_key = _check.not_none(
        value=DATE_PARTITION.get_last_partition_key()
    )

    for workbook_id in WORKBOOK_ID_PARTITION_KEYS:
        partition_key = MultiPartitionKey(
            {"workbook_id_partition": workbook_id, "date": last_date_partition_key}
        )

        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
            tags={"tableau_pat_session_limit": "true"},
        )


tableau_workbook_refresh_schedules = [
    build_tableau_workbook_refresh_schedule(asset=asset)
    for asset in external_assets
    if asset.metadata_by_key[asset.key].get("cron_schedule") is not None
]

schedules = [
    tableau_workbook_asset_job_schedule,
    *tableau_workbook_refresh_schedules,
]
