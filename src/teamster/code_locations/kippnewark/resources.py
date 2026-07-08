from dagster import EnvVar

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.libraries.finalsite.api.resources import FinalsiteResource

# NOTE: server defaults to CODE_LOCATION ("kippnewark") →
# kippnewark.fsenrollment.com. Confirm Newark's actual Finalsite subdomain
# before deploy (see plan "Open config value"); pass an explicit string here if
# it differs.
FINALSITE_RESOURCE = FinalsiteResource(
    server=CODE_LOCATION,
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)
