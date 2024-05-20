from dagster import define_asset_job

from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.smartrecruiters.assets import smartrecruiters_report_assets

smartrecruiters_report_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_smartrecruiters_report_asset_job",
    selection=smartrecruiters_report_assets,
)

jobs = [
    smartrecruiters_report_asset_job,
]
