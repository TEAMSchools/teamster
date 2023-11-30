from dagster import define_asset_job

from ... import CODE_LOCATION
from .assets import google_forms_assets

google_forms_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_google_forms_asset_job",
    selection=[a.key for a in google_forms_assets],
)
