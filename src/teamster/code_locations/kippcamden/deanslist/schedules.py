from dagster import AssetKey

from teamster.code_locations.kippcamden import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippcamden.deanslist.assets import assets
from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

deanslist_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

deanslist_midday_commlog_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__midday_commlog_job",
    cron_schedule="0 14 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[
        a for a in assets if a.key == AssetKey([CODE_LOCATION, "deanslist", "comm_log"])
    ],
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

schedules = [
    deanslist_partitioned_assets_job_schedule,
    deanslist_midday_commlog_job_schedule,
]
