import pathlib

from dagster import config_from_files

from teamster.kipptaf import CODE_LOCATION
from teamster.smartrecruiters.assets import build_smartrecruiters_report_asset

smartrecruiters_report_assets = [
    build_smartrecruiters_report_asset(code_location=CODE_LOCATION, **a)
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]

assets = [
    *smartrecruiters_report_assets,
]
