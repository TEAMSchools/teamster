from dagster import config_from_files

from teamster.core.google.sheets.assets import build_gsheet_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/google/config"

gsheet_assets = [
    build_gsheet_asset(code_location=CODE_LOCATION, **asset)
    for asset in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *gsheet_assets,
]
