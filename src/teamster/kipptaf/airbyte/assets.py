from dagster import config_from_files
from dagster_airbyte import build_airbyte_assets

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/airbyte/config"

airbyte_assets = [
    build_airbyte_assets(**a, asset_key_prefix=[CODE_LOCATION])
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *airbyte_assets,
]
