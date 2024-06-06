from dagster import define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.google.forms.assets import form, responses

google_forms_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_google_forms_asset_job", selection=[form, responses]
)

jobs = [
    google_forms_asset_job,
]
