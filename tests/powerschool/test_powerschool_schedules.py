from dagster import EnvVar, build_schedule_context

from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kippnewark.powerschool.schedules import last_modified_schedule


def test_schedule():
    context = build_schedule_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    output = last_modified_schedule(
        context=context,
        ssh_powerschool=SSHResource(
            remote_host="psteam.kippnj.org",
            remote_port=EnvVar("KIPPNEWARK_PS_SSH_PORT").get_value(),
            username=EnvVar("KIPPNEWARK_PS_SSH_USERNAME"),
            password=EnvVar("KIPPNEWARK_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("KIPPNEWARK_PS_SSH_REMOTE_BIND_HOST"),
        ),
        db_powerschool=OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="oracledb",
                username="PSNAVIGATOR",
                host="localhost",
                database="PSPRODDB",
                port=1521,
                password=EnvVar("KIPPNEWARK_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
    )

    for o in output:
        context.log.info(o)
