import pathlib

from dagster import config_from_files

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.extracts.assets import build_bigquery_query_sftp_asset

config_dir = pathlib.Path(__file__).parent / "config"

parentsquare_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/parentsquare.yaml"])["assets"]
]

powerschool_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/powerschool.yaml"])["assets"]
]

assets = [
    *parentsquare_extract_assets,
    *powerschool_extract_assets,
]
