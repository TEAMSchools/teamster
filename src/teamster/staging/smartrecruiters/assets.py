from dagster import config_from_files

from teamster.core.smartrecruiters.assets import build_smartrecruiters_report_asset

from .. import CODE_LOCATION

SOURCE_SYSTEM = "smartrecruiters"

config_dir = f"src/teamster/{CODE_LOCATION}/{SOURCE_SYSTEM}/config"

smartrecruiters_report_assets = [
    build_smartrecruiters_report_asset(
        code_location=CODE_LOCATION, source_system=SOURCE_SYSTEM, **a
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

__all__ = [
    *smartrecruiters_report_assets,
]
