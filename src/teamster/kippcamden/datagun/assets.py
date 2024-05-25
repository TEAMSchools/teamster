import pathlib

from dagster import config_from_files

from teamster.core.datagun.assets import build_bigquery_extract_asset
from teamster.kippcamden import LOCAL_TIMEZONE

powerschool_extract_assets = [
    build_bigquery_extract_asset(timezone=LOCAL_TIMEZONE, **a)
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/powerschool.yaml"]
    )["assets"]
]

assets = [
    *powerschool_extract_assets,
]
