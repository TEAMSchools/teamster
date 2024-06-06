from dagster import (
    RunRequest,
    ScheduleDefinition,
    build_schedule_from_partitioned_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.schoolmint.grow.jobs import (
    multi_partition_asset_job,
    schoolmint_grow_user_update_job,
    static_partition_asset_job,
)


@schedule(
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=static_partition_asset_job,
)
def schoolmint_grow_static_partition_asset_job_schedule():
    for archived in ["t", "f"]:
        yield RunRequest(
            run_key=f"{CODE_LOCATION}_schoolmint_grow_static_partition_{archived}",
            partition_key=archived,
        )


multi_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=multi_partition_asset_job, hour_of_day=0, minute_of_hour=0
)

schoolmint_grow_user_update_job_schedule = ScheduleDefinition(
    cron_schedule="0 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=schoolmint_grow_user_update_job,
)

schedules = [
    schoolmint_grow_static_partition_asset_job_schedule,
    multi_partition_asset_job_schedule,
    schoolmint_grow_user_update_job_schedule,
]
