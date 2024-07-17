from dagster import AssetKey

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.deanslist.assets import (
    DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
    DEANSLIST_MONTHLY_MULTI_PARTITIONS_DEF,
    DEANSLIST_STATIC_PARTITIONS_DEF,
    fiscal_multi_partitions_assets,
    monthly_multi_partitions_assets,
    static_partitions_assets,
)
from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

deanslist_static_partitions_assets_job_schedule = build_deanslist_job_schedule(
    job_name=f"{CODE_LOCATION}_deanslist_static_partitions_assets_job",
    selection=static_partitions_assets,
    partitions_def=DEANSLIST_STATIC_PARTITIONS_DEF,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_monthly_multi_partitions_assets_job_schedule = build_deanslist_job_schedule(
    job_name=f"{CODE_LOCATION}_deanslist_monthly_multi_partitions_assets_job",
    selection=monthly_multi_partitions_assets,
    partitions_def=DEANSLIST_MONTHLY_MULTI_PARTITIONS_DEF,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_fiscal_multi_partitions_assets_job_schedule = build_deanslist_job_schedule(
    job_name=f"{CODE_LOCATION}_deanslist_fiscal_multi_partitions_assets_job",
    selection=fiscal_multi_partitions_assets,
    partitions_def=DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

deanslist_midday_commlog_job_schedule = build_deanslist_job_schedule(
    job_name=f"{CODE_LOCATION}_deanslist_midday_commlog_job",
    selection=[AssetKey([CODE_LOCATION, "deanslist", "comm_log"])],
    partitions_def=DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
    cron_schedule="0 14 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    deanslist_fiscal_multi_partitions_assets_job_schedule,
    deanslist_midday_commlog_job_schedule,
    deanslist_monthly_multi_partitions_assets_job_schedule,
    deanslist_static_partitions_assets_job_schedule,
]
