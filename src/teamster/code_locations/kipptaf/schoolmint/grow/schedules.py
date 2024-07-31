from typing import Generator

from dagster import (
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    build_schedule_from_partitioned_job,
    define_asset_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.schoolmint.grow.assets import (
    schoolmint_grow_multi_partitions_assets,
    schoolmint_grow_static_partitions_assets,
)
from teamster.code_locations.kipptaf.schoolmint.grow.jobs import (
    schoolmint_grow_user_update_job,
)

job = define_asset_job(
    name=f"{CODE_LOCATION}_schoolmint_grow_static_partitions_assets_job",
    selection=schoolmint_grow_static_partitions_assets,
)


@schedule(
    name=f"{job.name}_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=job,
)
def schoolmint_grow_static_partitions_assets_job_schedule(
    context: ScheduleEvaluationContext,
) -> Generator:
    for partition_key in ["t", "f"]:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{partition_key}",
            partition_key=partition_key,
        )


schoolmint_grow_multi_partitions_assets_job_schedule = (
    build_schedule_from_partitioned_job(
        job=define_asset_job(
            name=f"{CODE_LOCATION}_schoolmint_grow_multi_partitions_assets_job",
            selection=schoolmint_grow_multi_partitions_assets,
        ),
        hour_of_day=0,
        minute_of_hour=0,
    )
)

schoolmint_grow_user_update_job_schedule = ScheduleDefinition(
    cron_schedule="30 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_user_update_job,
)

schedules = [
    schoolmint_grow_multi_partitions_assets_job_schedule,
    schoolmint_grow_static_partitions_assets_job_schedule,
    schoolmint_grow_user_update_job_schedule,
]
