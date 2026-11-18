from dagster import (
    MultiPartitionKey,
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    define_asset_job,
    in_process_executor,
    schedule,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.level_data.grow.assets import (
    MULTI_PARTITIONS_DEF,
    grow_multi_partitions_assets,
    grow_static_partition_assets,
    grow_user_sync,
)

grow_user_sync_schedule = ScheduleDefinition(
    name=f"{grow_user_sync.key.to_python_identifier()}_schedule",
    target=define_asset_job(
        name=f"{grow_user_sync.key.to_python_identifier()}_asset_job",
        selection=[grow_user_sync],
        executor_def=in_process_executor,
    ),
    cron_schedule="20 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)


# In process: a step pod per asset adds to the 02:00 pod burst that GKE preempts
# on new nodes (#6225). Each step is a few seconds of API work, so loading the
# code location once and running the steps in turn is faster than a child process
# per step, and the default run pod fits on an existing node.
grow_static_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__grow__static_partition_assets_job",
    selection=grow_static_partition_assets,
    executor_def=in_process_executor,
)


@schedule(
    name=f"{CODE_LOCATION}__grow__static_partition_assets_schedule",
    target=grow_static_partition_asset_job,
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
def grow_static_partition_asset_job_schedule(context: ScheduleEvaluationContext):
    for partition_key in ["t", "f"]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
        )


@schedule(
    name=f"{CODE_LOCATION}__grow__multi_partition_assets_schedule",
    target=grow_multi_partitions_assets,
    cron_schedule=["0 5 * * *", "0 11 * * *", "0 14 * * *", "45 15 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
)
def grow_multi_partition_asset_job_schedule(context: ScheduleEvaluationContext):
    for archived in MULTI_PARTITIONS_DEF.get_partitions_def_for_dimension(
        "archived"
    ).get_partition_keys():
        partition_key = MultiPartitionKey(
            {
                "archived": archived,
                "last_modified": check.not_none(
                    value=MULTI_PARTITIONS_DEF.get_partitions_def_for_dimension(
                        "last_modified"
                    ).get_last_partition_key()
                ),
            }
        )

        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
        )


schedules = [
    grow_multi_partition_asset_job_schedule,
    grow_static_partition_asset_job_schedule,
    grow_user_sync_schedule,
]
