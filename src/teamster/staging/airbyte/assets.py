from dagster import config_from_files

from teamster.core.airbyte.assets import build_airbyte_cloud_assets
from teamster.staging import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/airbyte/config"

__all__ = []

for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
    __all__.extend(
        build_airbyte_cloud_assets(
            **a, asset_key_prefix=[CODE_LOCATION, a["group_name"]]
        )
    )
