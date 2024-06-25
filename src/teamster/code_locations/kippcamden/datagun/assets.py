import pathlib

from dagster import config_from_files

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.datagun.assets import build_bigquery_extract_asset

powerschool_extract_assets = [
    build_bigquery_extract_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/powerschool.yaml"]
    )["assets"]
]

assets = [
    *powerschool_extract_assets,
]
