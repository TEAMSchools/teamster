import logging

import pytest
from dagster import EnvVar, build_resources
from dagster_shared import check
from sqlalchemy import text

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import powerschool_connection
from teamster.libraries.ssh.resources import SSHResource

DISTRICTS = ["KIPPNEWARK", "KIPPCAMDEN", "KIPPMIAMI"]


def _get_env(name: str, district: str) -> str:
    """Resolve a district-specific env var via EnvVar."""
    return check.not_none(EnvVar(f"{name}_{district}").get_value())


@pytest.mark.parametrize("district", DISTRICTS)
def test_powerschool_odbc_resource_connects_and_queries(district: str):
    with build_resources(
        resources={
            "ssh_powerschool": SSHResource(
                remote_host=_get_env("PS_SSH_HOST", district),
                remote_port=int(_get_env("PS_SSH_PORT", district)),
                username=_get_env("PS_SSH_USERNAME", district),
                password=_get_env("PS_SSH_PASSWORD", district),
                tunnel_remote_host=_get_env("PS_SSH_REMOTE_BIND_HOST", district),
                test=True,
            ),
            "db_powerschool": PowerSchoolODBCResource(
                user=_get_env("PS_DB_USERNAME", district),
                password=_get_env("PS_DB_PASSWORD", district),
                host=_get_env("PS_DB_HOST", district),
                port=_get_env("PS_DB_PORT", district),
                service_name=_get_env("PS_DB_DATABASE", district),
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
