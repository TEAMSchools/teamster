from dagster import AssetKey

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.deanslist.jobs import (
    multi_partition_fiscal_asset_job,
    multi_partition_monthly_asset_job,
    static_partition_asset_job,
)
from teamster.libraries.deanslist.schedules import (
    build_deanslist_multi_partition_asset_job_schedule,
    build_deanslist_static_partition_asset_job_schedule,
)

deanslist_static_partition_asset_job_schedule = (
    build_deanslist_static_partition_asset_job_schedule(
        code_location=CODE_LOCATION,
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
        job=static_partition_asset_job,
    )
)

deanslist_multi_partition_monthly_asset_job_schedule = (
    build_deanslist_multi_partition_asset_job_schedule(
        code_location=CODE_LOCATION,
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
        job=multi_partition_monthly_asset_job,
    )
)

deanslist_multi_partition_fiscal_asset_job_schedule = (
    build_deanslist_multi_partition_asset_job_schedule(
        code_location=CODE_LOCATION,
        cron_schedule="0 0 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
        job=multi_partition_fiscal_asset_job,
    )
)

deanslist_comm_log_midday_job_schedule = (
    build_deanslist_multi_partition_asset_job_schedule(
        code_location=CODE_LOCATION,
        cron_schedule="0 14 * * *",
        execution_timezone=LOCAL_TIMEZONE.name,
        job=multi_partition_fiscal_asset_job,
        asset_selection=[AssetKey([CODE_LOCATION, "deanslist", "comm_log"])],
        schedule_name=(
            f"{CODE_LOCATION}_deanslist_multi_partition_comm_log_asset_job_schedule"
        ),
    )
)

schedules = [
    deanslist_comm_log_midday_job_schedule,
    deanslist_multi_partition_fiscal_asset_job_schedule,
    deanslist_multi_partition_monthly_asset_job_schedule,
    deanslist_static_partition_asset_job_schedule,
]
