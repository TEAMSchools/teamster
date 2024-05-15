from teamster.core.dbt.schedules import build_dbt_code_version_schedule
from teamster.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.kipptaf.dbt.assets import dbt_assets

dbt_code_version_schedule = build_dbt_code_version_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="*/10 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    dbt_assets=dbt_assets,
)

schedules = [
    dbt_code_version_schedule,
]
