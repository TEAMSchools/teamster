from dagster import EnvVar, build_resources
from sqlalchemy import TextClause

from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource


def test():
    with build_resources(
        resources={
            "ssh_powerschool": SSHResource(
                remote_host=EnvVar("PS_SSH_HOST"),
                remote_port=int(EnvVar("PS_SSH_PORT")),
                username=EnvVar("PS_SSH_USERNAME"),
                tunnel_remote_host=EnvVar("PS_SSH_REMOTE_BIND_HOST"),
            ),
            "db_powerschool": PowerSchoolODBCResource(
                user=EnvVar("PS_DB_USERNAME"),
                password=EnvVar("PS_DB_PASSWORD"),
                host=EnvVar("PS_DB_HOST"),
                port=EnvVar("PS_DB_PORT"),
                service_name=EnvVar("PS_DB_DATABASE"),
            ),
        }
    ) as resources:
        ssh_powerschool: SSHResource = resources.ssh_powerschool
        db_powerschool: PowerSchoolODBCResource = resources.db_powerschool

    ssh_tunnel = ssh_powerschool.open_ssh_tunnel()

    try:
        connection = db_powerschool.connect()
    except Exception as e:
        ssh_tunnel.kill()
        raise e

    result = db_powerschool.execute_query(
        connection=connection,
        query=TextClause("SELECT network_service_banner FROM v$session_connect_info"),
    )

    print(result)
