import json

from dagster import EnvVar, build_sensor_context, instance_for_test
from dagster_ssh import SSHResource

from teamster.core.powerschool.sensors import build_partition_sensor
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.kippnewark import LOCAL_TIMEZONE
from teamster.kippnewark.powerschool.assets import partition_assets

CURSOR = {
    "kippnewark__powerschool__assignmentscore": 1600000000.0,
    # "kippnewark__powerschool__assignmentcategoryassoc": 1700082000.0,
    # "kippnewark__powerschool__assignmentsection": 1700082000.0,
    # "kippnewark__powerschool__attendance": 1700082000.0,
    # "kippnewark__powerschool__pgfinalgrades": 1700082000.0,
    # "kippnewark__powerschool__storedgrades": 1700082000.0,
}


def test_sensor():
    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance, cursor=json.dumps(CURSOR))

        dynamic_partition_sensor = build_partition_sensor(
            name="test", asset_defs=partition_assets, timezone=LOCAL_TIMEZONE.name
        )

        sensor_results = dynamic_partition_sensor(
            context=context,
            ssh_powerschool=SSHResource(
                remote_host="psteam.kippnj.org",
                remote_port=EnvVar("KIPPNEWARK_PS_SSH_PORT"),
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
