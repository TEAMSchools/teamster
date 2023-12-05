from dagster import FreshnessPolicy, config_from_files

from teamster.core.amplify.assets import build_mclass_asset

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/amplify/config"

mclass_assets = [
    build_mclass_asset(
        code_location=CODE_LOCATION,
        timezone=LOCAL_TIMEZONE,
        freshness_policy=FreshnessPolicy(
            maximum_lag_minutes=(60 * 24),
            cron_schedule="0 0 * * *",
            cron_schedule_timezone=LOCAL_TIMEZONE.name,
        ),
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *mclass_assets,
]
