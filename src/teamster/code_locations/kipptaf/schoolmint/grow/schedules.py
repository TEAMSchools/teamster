from dagster import (
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    _check,
    build_schedule_from_partitioned_job,
    define_asset_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.schoolmint.grow.assets import (
    assignments,
    observations,
    schoolmint_grow_static_partition_assets,
)
from teamster.code_locations.kipptaf.schoolmint.grow.jobs import (
    schoolmint_grow_user_update_job,
)

schoolmint_grow_user_update_job_schedule = ScheduleDefinition(
    cron_schedule="0 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_user_update_job,
)

schoolmint_grow_assignments_job_schedule = build_schedule_from_partitioned_job(
    job=define_asset_job(
        name=f"{assignments.key.to_python_identifier()}_job", selection=[assignments]
    ),
    hour_of_day=0,
    minute_of_hour=0,
)


schoolmint_grow_static_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__schoolmint__grow__static_partition_asset_job",
    selection=schoolmint_grow_static_partition_assets,
)


@schedule(
    name=f"{schoolmint_grow_static_partition_asset_job.name}_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_static_partition_asset_job,
)
def schoolmint_grow_static_partition_asset_job_schedule(
    context: ScheduleEvaluationContext,
):
    for partition_key in ["t", "f"]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
        )


schoolmint_grow_observations_asset_job = define_asset_job(
    name=f"{observations.key.to_python_identifier()}_job",
    selection=[observations],
    partitions_def=observations.partitions_def,
)


@schedule(
    name=f"{schoolmint_grow_observations_asset_job.name}_schedule",
    cron_schedule=["0 0 * * *", "0 14 * * *", "45 15 * * *"],
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_observations_asset_job,
)
def schoolmint_grow_observations_asset_job_schedule(
    context: ScheduleEvaluationContext,
):
    multi_partitions_def = _check.inst(
        obj=schoolmint_grow_observations_asset_job.partitions_def,
        ttype=MultiPartitionsDefinition,
    )

    archived_partitions_def = multi_partitions_def.get_partitions_def_for_dimension(
        "archived"
    )
    last_modified_partitions_def = (
        multi_partitions_def.get_partitions_def_for_dimension("last_modified")
    )

    last_modified_partition_key = _check.not_none(
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
    schoolmint_grow_assignments_job_schedule,
    schoolmint_grow_observations_asset_job_schedule,
    schoolmint_grow_static_partition_asset_job_schedule,
    schoolmint_grow_user_update_job_schedule,
]
