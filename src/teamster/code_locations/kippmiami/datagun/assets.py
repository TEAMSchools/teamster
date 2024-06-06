from dagster import config_from_files

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.datagun.assets import build_bigquery_extract_asset

config_dir = f"src/teamster/{CODE_LOCATION}/datagun/config"

powerschool_extract_assets = [
    build_bigquery_extract_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/powerschool.yaml"])["assets"]
]

assets = [
    *powerschool_extract_assets,
]
