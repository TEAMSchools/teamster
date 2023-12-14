from dagster import define_asset_job

from ... import CODE_LOCATION
from .assets import form, responses

google_forms_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_google_forms_asset_job", selection=[form, responses]
)

_all = [
    google_forms_asset_job,
]
