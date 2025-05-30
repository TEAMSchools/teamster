from dagster import AssetKey

from teamster.code_locations.kippmiami import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippmiami.deanslist.assets import (
    month_partitioned_assets,
    static_partitioned_assets,
    year_partitioned_assets,
)
from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

deanslist_static_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__static_partitioned_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=static_partitioned_assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

deanslist_month_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__month_partitioned_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=month_partitioned_assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

deanslist_year_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__year_partitioned_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=year_partitioned_assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

deanslist_midday_commlog_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__midday_commlog_job",
    cron_schedule="0 14 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[
        a
        for a in year_partitioned_assets
        if a.key == AssetKey([CODE_LOCATION, "deanslist", "comm_log"])
    ],
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

schedules = [
    deanslist_midday_commlog_job_schedule,
    deanslist_month_partitioned_assets_job_schedule,
    deanslist_static_partitioned_assets_job_schedule,
    deanslist_year_partitioned_assets_job_schedule,
]
