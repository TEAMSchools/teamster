from dagster import define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.smartrecruiters.assets import assets

smartrecruiters_report_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_smartrecruiters_report_asset_job", selection=assets
)

jobs = [
    smartrecruiters_report_asset_job,
]
