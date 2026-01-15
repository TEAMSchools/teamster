from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark._dbt.assets import dbt_assets
from teamster.libraries.dbt.schedules import build_dbt_code_version_schedule

dbt_code_version_schedule = build_dbt_code_version_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="*/10 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    dbt_assets=dbt_assets,
)

schedules = [
    dbt_code_version_schedule,
]
