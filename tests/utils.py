from dagster import EnvVar
from dagster_shared import check

from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource


def get_ssh_powerschool_resource(code_location: str):
    return SSHResource(
        remote_host=EnvVar(f"PS_SSH_HOST_{code_location}"),
        remote_port=int(
            check.not_none(value=EnvVar(f"PS_SSH_PORT_{code_location}").get_value())
        ),
        username=EnvVar(f"PS_SSH_USERNAME_{code_location}"),
        password=EnvVar(f"PS_SSH_PASSWORD_{code_location}"),
        tunnel_remote_host=EnvVar(f"PS_SSH_REMOTE_BIND_HOST_{code_location}"),
        test=True,
    )


def get_db_powerschool_resource(code_location: str):
    return PowerSchoolODBCResource(
        user=EnvVar(f"PS_DB_USERNAME_{code_location}"),
        password=EnvVar(f"PS_DB_PASSWORD_{code_location}"),
        host=EnvVar(f"PS_DB_HOST_{code_location}"),
        port=EnvVar(f"PS_DB_PORT_{code_location}"),
        service_name=EnvVar(f"PS_DB_DATABASE_{code_location}"),
    )


def get_titan_ssh_resource(code_location: str):
    code_location = code_location.upper()

    return SSHResource(
        remote_host="sftp.titank12.com",
        username=EnvVar(f"TITAN_SFTP_USERNAME_{code_location}"),
        password=EnvVar(f"TITAN_SFTP_PASSWORD_{code_location}"),
    )


def get_renlearn_ssh_resource(code_location: str):
    code_location = code_location.upper()

    return SSHResource(
        remote_host="sftp.renaissance.com",
        username=EnvVar(f"RENLEARN_SFTP_USERNAME_{code_location}"),
        password=EnvVar(f"RENLEARN_SFTP_PASSWORD_{code_location}"),
    )
