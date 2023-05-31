from dagster import config_from_files

from teamster.core.amplify.assets import build_mclass_asset

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/amplify/config"

mclass_assets = [
    build_mclass_asset(
        code_location=CODE_LOCATION,
        source_system="amplify",
        timezone=LOCAL_TIMEZONE,
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *mclass_assets,
]
