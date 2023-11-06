from teamster.core.dbt.schedules import build_dbt_code_version_schedule

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import _dbt_assets

dbt_code_version_schedule = build_dbt_code_version_schedule(
    code_location=CODE_LOCATION,
    cron_schedule="*/5 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    dbt_assets=_dbt_assets,
)

__all__ = [
    dbt_code_version_schedule,
]
