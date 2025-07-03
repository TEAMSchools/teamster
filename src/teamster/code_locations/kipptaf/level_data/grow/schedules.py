from dagster import (
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    build_schedule_from_partitioned_job,
    define_asset_job,
    schedule,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.level_data.grow.assets import assignments
from teamster.code_locations.kipptaf.level_data.grow.jobs import (
    grow_observations_asset_job,
    grow_static_partition_asset_job,
    grow_user_update_job,
)

grow_user_update_job_schedule = ScheduleDefinition(
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    job=grow_user_update_job,
)

grow_assignments_job_schedule = build_schedule_from_partitioned_job(
    job=define_asset_job(
        name=f"{assignments.key.to_python_identifier()}_job", selection=[assignments]
    ),
    hour_of_day=5,
    minute_of_hour=0,
)


@schedule(
    name=f"{grow_static_partition_asset_job.name}_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    job=grow_static_partition_asset_job,
)
def grow_static_partition_asset_job_schedule(context: ScheduleEvaluationContext):
    for partition_key in ["t", "f"]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
        )


@schedule(
    name=f"{grow_observations_asset_job.name}_schedule",
    cron_schedule=["15 11 * * *", "15 13 * * *", "15 15 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
    job=grow_observations_asset_job,
)
def grow_observations_asset_job_schedule(context: ScheduleEvaluationContext):
    multi_partitions_def = check.inst(
        obj=grow_observations_asset_job.partitions_def, ttype=MultiPartitionsDefinition
    )

    archived_partitions_def = multi_partitions_def.get_partitions_def_for_dimension(
        "archived"
    )
    last_modified_partitions_def = (
        multi_partitions_def.get_partitions_def_for_dimension("last_modified")
    )

    last_modified_partition_key = check.not_none(
        value=last_modified_partitions_def.get_last_partition_key()
    )

    for archived_partition_key in archived_partitions_def.get_partition_keys():
        partition_key = MultiPartitionKey(
            {
                "archived": archived_partition_key,
                "last_modified": last_modified_partition_key,
            }
        )

        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
        )


schedules = [
    grow_assignments_job_schedule,
    grow_observations_asset_job_schedule,
    grow_static_partition_asset_job_schedule,
    grow_user_update_job_schedule,
]
