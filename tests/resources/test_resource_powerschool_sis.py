import logging

from dagster import EnvVar, build_resources
from sqlalchemy import text

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import powerschool_connection
from teamster.libraries.ssh.resources import SSHResource


def test_powerschool_odbc_resource_connects_and_queries():
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

    log = logging.getLogger(__name__)

    with powerschool_connection(ssh_powerschool, db_powerschool, log) as connection:
        result = db_powerschool.execute_query(
            connection=connection,
            query=text("SELECT network_service_banner FROM v$session_connect_info"),
        )

    assert isinstance(result, list)
    assert len(result) > 0
