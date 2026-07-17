from dagster import EnvVar

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.finalsite.api.resources import FinalsiteResource
from teamster.libraries.ssh.resources import SSHResource

FINALSITE_RESOURCE = FinalsiteResource(
    server=CODE_LOCATION,
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)

SSH_POWERSCHOOL = SSHResource(
    remote_host=EnvVar("PS_SSH_HOST"),
    remote_port=EnvVar.int("PS_SSH_PORT"),
    username=EnvVar("PS_SSH_USERNAME"),
    password=EnvVar("PS_SSH_PASSWORD"),
    tunnel_remote_host=EnvVar("PS_SSH_REMOTE_BIND_HOST"),
    enable_legacy_rsa=True,
)
