from dagster import Definitions, EnvVar, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.core.ssh.resources import SSHResource
from teamster.kipptaf import ldap
from teamster.kipptaf.adp.workforce_now import sftp as adp_wfn_sftp
from teamster.kipptaf.ldap.resources import LdapResource

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            adp_wfn_sftp,
            ldap,
        ]
    ),
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
        "ldap": LdapResource(
            # host="ldap1.kippnj.org",
            host="204.8.89.213",
            port=636,
            user=EnvVar("LDAP_USER"),
            password=EnvVar("LDAP_PASSWORD"),
        ),
        "ssh_adp_workforce_now": SSHResource(
            # remote_host="sftp.kippnj.org",
            remote_host="204.8.89.221",
            username=EnvVar("ADP_SFTP_USERNAME"),
            password=EnvVar("ADP_SFTP_PASSWORD"),
        ),
    },
)
