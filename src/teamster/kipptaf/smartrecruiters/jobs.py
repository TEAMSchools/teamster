from dagster import AssetSelection, define_asset_job

from .. import CODE_LOCATION
from .assets import smartrecruiters_report_assets

smartrecruiters_report_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_smartrecruiters_report_asset_job",
    selection=AssetSelection.assets(*smartrecruiters_report_assets),
)

_all = [
    smartrecruiters_report_asset_job,
]
