import json

from dagster import EnvVar, build_sensor_context, instance_for_test

from teamster.core.powerschool.sensors import build_dynamic_partition_sensor
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.kippnewark import LOCAL_TIMEZONE
from teamster.kippnewark.powerschool.assets import partition_assets

CURSOR = {
    "kippnewark__powerschool__attendance": 1689012240.0,
    "kippnewark__powerschool__cc": 1690381980.0,
    "kippnewark__powerschool__courses": 1689862140.0,
    "kippnewark__powerschool__pgfinalgrades": 1689012240.0,
    "kippnewark__powerschool__prefs": 1690381980.0,
    "kippnewark__powerschool__schools": 1689862140.0,
    "kippnewark__powerschool__sections": 1690381980.0,
    "kippnewark__powerschool__storedgrades": 1690360380.0,
    "kippnewark__powerschool__students": 1690381980.0,
    "kippnewark__powerschool__termbins": 1689012240.0,
    "kippnewark__powerschool__terms": 1690299180.0,
    "kippnewark__powerschool__assignmentcategoryassoc": 1689012240.0,
    "kippnewark__powerschool__assignmentscore": 1689012240.0,
    "kippnewark__powerschool__assignmentsection": 1689012240.0,
    "kippnewark__powerschool__codeset": 1689012240.0,
    "kippnewark__powerschool__districtteachercategory": 1689012240.0,
    "kippnewark__powerschool__emailaddress": 1690381980.0,
    "kippnewark__powerschool__gradecalcformulaweight": 1689012240.0,
    "kippnewark__powerschool__gradecalcschoolassoc": 1689012240.0,
    "kippnewark__powerschool__gradecalculationtype": 1689012240.0,
    "kippnewark__powerschool__gradeformulaset": 1689012240.0,
    "kippnewark__powerschool__gradescaleitem": 1689012240.0,
    "kippnewark__powerschool__gradeschoolconfig": 1689012240.0,
    "kippnewark__powerschool__gradeschoolformulaassoc": 1689012240.0,
    "kippnewark__powerschool__gradesectionconfig": 1689012240.0,
    "kippnewark__powerschool__originalcontactmap": 1690381980.0,
    "kippnewark__powerschool__person": 1690381980.0,
    "kippnewark__powerschool__personaddress": 1690381980.0,
    "kippnewark__powerschool__personaddressassoc": 1690381980.0,
    "kippnewark__powerschool__personemailaddressassoc": 1690381980.0,
    "kippnewark__powerschool__personphonenumberassoc": 1690381980.0,
    "kippnewark__powerschool__phonenumber": 1690381980.0,
    "kippnewark__powerschool__roledef": 1689012240.0,
    "kippnewark__powerschool__s_nj_crs_x": 1689858480.0,
    "kippnewark__powerschool__s_nj_ren_x": 1690381980.0,
    "kippnewark__powerschool__s_nj_stu_x": 1690381980.0,
    "kippnewark__powerschool__s_nj_usr_x": 1689012240.0,
    "kippnewark__powerschool__schoolstaff": 1690299180.0,
    "kippnewark__powerschool__sectionteacher": 1690299180.0,
    "kippnewark__powerschool__studentcontactassoc": 1690381980.0,
    "kippnewark__powerschool__studentcontactdetail": 1690381980.0,
    "kippnewark__powerschool__studentcorefields": 1690381980.0,
    "kippnewark__powerschool__studentrace": 1690381980.0,
    "kippnewark__powerschool__teachercategory": 1689012240.0,
    "kippnewark__powerschool__u_clg_et_stu": 1690381980.0,
    "kippnewark__powerschool__u_clg_et_stu_alt": 1690381980.0,
    "kippnewark__powerschool__u_def_ext_students": 1690381980.0,
    "kippnewark__powerschool__u_studentsuserfields": 1690381980.0,
    "kippnewark__powerschool__users": 1689946260.0,
}


def test_sensor():
    with instance_for_test() as instance:
        context = build_sensor_context(instance=instance, cursor=json.dumps(CURSOR))

        dynamic_partition_sensor = build_dynamic_partition_sensor(
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
