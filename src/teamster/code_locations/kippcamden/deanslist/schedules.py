from dagster import AssetKey

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.deanslist.assets import (
    multi_partition_fiscal_assets,
    multi_partition_monthly_assets,
    static_partition_assets,
)
from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

deanslist_static_partition_asset_job_schedule = build_deanslist_job_schedule(
    code_location=CODE_LOCATION,
    partitions_type="static",
    selection=static_partition_assets,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_multi_partition_monthly_asset_job_schedule = build_deanslist_job_schedule(
    code_location=CODE_LOCATION,
    partitions_type="monthly",
    selection=multi_partition_monthly_assets,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_multi_partition_fiscal_asset_job_schedule = build_deanslist_job_schedule(
    code_location=CODE_LOCATION,
    partitions_type="fiscal",
    selection=multi_partition_fiscal_assets,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_comm_log_midday_job_schedule = build_deanslist_job_schedule(
    code_location=CODE_LOCATION,
    partitions_type="comm_log",
    selection=[AssetKey([CODE_LOCATION, "deanslist", "comm_log"])],
    cron_schedule="0 14 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    deanslist_comm_log_midday_job_schedule,
    deanslist_multi_partition_fiscal_asset_job_schedule,
    deanslist_multi_partition_monthly_asset_job_schedule,
    deanslist_static_partition_asset_job_schedule,
]
