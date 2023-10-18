import json

from dagster import EnvVar, build_sensor_context, instance_for_test

from teamster.core.powerschool.sensors import build_partition_sensor
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.kippnewark import LOCAL_TIMEZONE
from teamster.kippnewark.powerschool.assets import partition_assets

CURSOR = {
    "kippnewark__powerschool__attendance__2016-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2017-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2018-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2019-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2020-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2021-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2022-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__attendance__2023-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2016-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2017-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2018-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2019-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2020-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2021-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2022-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__pgfinalgrades__2023-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2016-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2017-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2018-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2019-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2020-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2021-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2022-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__storedgrades__2023-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2016-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2017-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2018-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2019-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2020-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2021-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2022-07-01T00:00:00-0400": 1690836840.0,
    "kippnewark__powerschool__assignmentscore__2023-07-01T00:00:00-0400": 1690836840.0,
}


def test_sensor():
    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance, cursor=json.dumps(CURSOR))

        dynamic_partition_sensor = build_partition_sensor(
            name="test", asset_defs=partition_assets, timezone=LOCAL_TIMEZONE.name
        )

        sensor_results = dynamic_partition_sensor(
            context=context,
            ssh_powerschool=SSHConfigurableResource(
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
