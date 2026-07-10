from dagster import EnvVar

from teamster.code_locations.kippcamden import CODE_LOCATION
from teamster.libraries.finalsite.api.resources import FinalsiteResource

FINALSITE_RESOURCE = FinalsiteResource(
    server=CODE_LOCATION,
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)
