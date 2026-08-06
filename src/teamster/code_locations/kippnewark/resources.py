from dagster import EnvVar

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.libraries.finalsite.api.resources import FinalsiteResource
from teamster.libraries.ssh.resources import SSHResource

FINALSITE_RESOURCE = FinalsiteResource(
    server=CODE_LOCATION,
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)

# ParentSquare's district-level SFTP endpoint is sftp3.parentsquare.com; the
# username is issued when the connection is created in the ParentSquare admin UI.
# All three variables map to the `op-parentsquare-sftp` Secret at both
# dagster-cloud.yaml insertion points. That Secret is synced by the
# OnePasswordItem in .k8s/1password/items.yaml, which is applied by hand — a
# secretKeyRef whose Secret or key does not exist fails container creation for
# the whole code server, so the apply and a key-name check both precede any
# deploy carrying these mappings. The Secret is shared across code locations, so
# moving these mappings here needed no new 1Password work.
SSH_RESOURCE_PARENTSQUARE = SSHResource(
    remote_host=EnvVar("PARENTSQUARE_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("PARENTSQUARE_SFTP_USERNAME"),
    password=EnvVar("PARENTSQUARE_SFTP_PASSWORD"),
)
