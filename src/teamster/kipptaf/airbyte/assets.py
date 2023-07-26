from dagster import config_from_files
from dagster_airbyte import build_airbyte_assets

from teamster.kipptaf import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/airbyte/config"

__all__ = []

for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
    __all__.extend(
        build_airbyte_assets(**a, asset_key_prefix=[CODE_LOCATION, a["group_name"]])
    )
