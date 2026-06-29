from dagster import EnvVar

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.finalsite.api.resources import FinalsiteResource
from teamster.libraries.ssh.resources import SSHResource

FINALSITE_RESOURCE = FinalsiteResource(
    server=CODE_LOCATION,
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)

SSH_FOCUS = SSHResource(
    remote_host=EnvVar("FOCUS_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("FOCUS_SFTP_USERNAME"),
    password=EnvVar("FOCUS_SFTP_PASSWORD"),
)
