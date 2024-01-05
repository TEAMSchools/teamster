from dagster import EnvVar, build_sensor_context

from teamster.core.powerschool.sensors import build_powerschool_sensor
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kippnewark.powerschool.assets import partition_assets


def test_sensor():
    context = build_sensor_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    dynamic_partition_sensor = build_powerschool_sensor(
        name="test", asset_defs=partition_assets
    )

    sensor_results = dynamic_partition_sensor(
        context=context,
        ssh_powerschool=SSHResource(
            remote_host="psteam.kippnj.org",
            remote_port=int(EnvVar("KIPPNEWARK_PS_SSH_PORT").get_value()),  # type: ignore
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

    for result in sensor_results:
        context.log.info(result)
