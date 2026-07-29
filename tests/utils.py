from dagster import EnvVar

from teamster.libraries.ssh.resources import SSHResource


def get_titan_ssh_resource(code_location: str):
    code_location = code_location.upper()

    return SSHResource(
        remote_host="sftp.titank12.com",
        remote_port=22,
        username=EnvVar(f"TITAN_SFTP_USERNAME_{code_location}"),
        password=EnvVar(f"TITAN_SFTP_PASSWORD_{code_location}"),
    )


def get_renlearn_ssh_resource(code_location: str):
    code_location = code_location.upper()

    return SSHResource(
        remote_host=EnvVar("RENLEARN_SFTP_HOST"),
        remote_port=22,
        username=EnvVar(f"RENLEARN_SFTP_USERNAME_{code_location}"),
        password=EnvVar(f"RENLEARN_SFTP_PASSWORD_{code_location}"),
    )
