from dagster import EnvVar

from teamster.libraries.finalsite.api.resources import FinalsiteResource

FINALSITE_RESOURCE = FinalsiteResource(
    server="kippmiami",
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)
