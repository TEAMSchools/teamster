import pathlib

from dagster import config_from_files

from teamster.core.datagun.assets import build_bigquery_extract_asset
from teamster.kippnewark import LOCAL_TIMEZONE

config_dir = pathlib.Path(__file__).parent / "config"

powerschool_extract_assets = [
    build_bigquery_extract_asset(timezone=LOCAL_TIMEZONE, **a)
    for a in config_from_files([f"{config_dir}/powerschool.yaml"])["assets"]
]

assets = [
    *powerschool_extract_assets,
]
