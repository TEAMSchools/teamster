from dagster import config_from_files

from teamster.core.smartrecruiters.assets import build_smartrecruiters_report_asset

from .. import CODE_LOCATION

smartrecruiters_report_assets = [
    build_smartrecruiters_report_asset(code_location=CODE_LOCATION, **a)
    for a in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/smartrecruiters/config/assets.yaml"]
    )["assets"]
]

__all__ = [
    *smartrecruiters_report_assets,
]
