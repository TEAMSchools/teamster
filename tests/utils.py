from dagster import EnvVar, _check

from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource


def get_ssh_powerschool_resource(code_location: str):
    return SSHResource(
        remote_host=EnvVar(f"PS_SSH_HOST_{code_location}"),
        remote_port=int(
            _check.not_none(value=EnvVar(f"PS_SSH_PORT_{code_location}").get_value())
        ),
        username=EnvVar(f"PS_SSH_USERNAME_{code_location}"),
        tunnel_remote_host=EnvVar(f"PS_SSH_REMOTE_BIND_HOST_{code_location}"),
    )


def get_db_powerschool_resource(code_location: str):
    return PowerSchoolODBCResource(
        user=EnvVar(f"PS_DB_USERNAME_{code_location}"),
        password=EnvVar(f"PS_DB_PASSWORD_{code_location}"),
        host=EnvVar(f"PS_DB_HOST_{code_location}"),
        port=EnvVar(f"PS_DB_PORT_{code_location}"),
        service_name=EnvVar(f"PS_DB_DATABASE_{code_location}"),
    )
