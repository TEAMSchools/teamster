from dagster import (
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
    schoolmint_grow_static_partitions_assets,
)
from teamster.code_locations.kipptaf.schoolmint.grow.jobs import (
    schoolmint_grow_user_update_job,
)

schoolmint_grow_user_update_job_schedule = ScheduleDefinition(
    cron_schedule="0 6 * * *",
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


schoolmint_grow_static_partitions_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__schoolmint_grow__static_partitions_asset_job",
    selection=schoolmint_grow_static_partitions_assets,
)


@schedule(
    name=f"{schoolmint_grow_static_partitions_asset_job.name}_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_static_partitions_asset_job,
)
def schoolmint_grow_static_partitions_assets_job_schedule(
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
    cron_schedule=["0 0 * * *", "0 14 * * *"],
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_observations_asset_job,
)
def schoolmint_grow_observations_asset_job_schedule(
    context: ScheduleEvaluationContext,
):
    partitions_def = _check.not_none(
        value=schoolmint_grow_observations_asset_job.partitions_def
    )

    partition_key = partitions_def.get_last_partition_key()

    yield RunRequest(
        run_key=f"{context._schedule_name}_{partition_key}", partition_key=partition_key
    )


schedules = [
    schoolmint_grow_assignments_job_schedule,
    schoolmint_grow_observations_asset_job_schedule,
    schoolmint_grow_static_partitions_assets_job_schedule,
    schoolmint_grow_user_update_job_schedule,
]
