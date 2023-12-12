import random

import pendulum
from dagster import MonthlyPartitionsDefinition, materialize

from teamster.core.powerschool.assets import build_powerschool_table_asset
from teamster.core.resources import (
    get_io_manager_gcs_avro,
    get_oracle_resource_powerschool,
    get_ssh_resource_powerschool,
)
from teamster.staging import LOCAL_TIMEZONE


def _test_asset(asset_name, partitions_def=None, partition_column=None):
    asset = build_powerschool_table_asset(
        code_location="staging",
        asset_name=asset_name,
        partitions_def=partitions_def,
        partition_column=partition_column,
    )

    if asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "db_powerschool": get_oracle_resource_powerschool("staging"),
            "ssh_powerschool": get_ssh_resource_powerschool("staging"),
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]
        .value
        > 0
    )


def test_asset_powerschool_cc():
    _test_asset(asset_name="cc")


def test_asset_powerschool_codeset():
    _test_asset(asset_name="codeset")


def test_asset_powerschool_courses():
    _test_asset(asset_name="courses")


def test_asset_powerschool_districtteachercategory():
    _test_asset(asset_name="districtteachercategory")


def test_asset_powerschool_emailaddress():
    _test_asset(asset_name="emailaddress")


def test_asset_powerschool_gradecalcformulaweight():
    _test_asset(asset_name="gradecalcformulaweight")


def test_asset_powerschool_gradecalcschoolassoc():
    _test_asset(asset_name="gradecalcschoolassoc")


def test_asset_powerschool_gradecalculationtype():
    _test_asset(asset_name="gradecalculationtype")


def test_asset_powerschool_gradeformulaset():
    _test_asset(asset_name="gradeformulaset")


def test_asset_powerschool_gradescaleitem():
    _test_asset(asset_name="gradescaleitem")


def test_asset_powerschool_gradeschoolconfig():
    _test_asset(asset_name="gradeschoolconfig")


def test_asset_powerschool_gradeschoolformulaassoc():
    _test_asset(asset_name="gradeschoolformulaassoc")


def test_asset_powerschool_gradesectionconfig():
    _test_asset(asset_name="gradesectionconfig")


def test_asset_powerschool_originalcontactmap():
    _test_asset(asset_name="originalcontactmap")


def test_asset_powerschool_person():
    _test_asset(asset_name="person")


def test_asset_powerschool_personaddress():
    _test_asset(asset_name="personaddress")


def test_asset_powerschool_personaddressassoc():
    _test_asset(asset_name="personaddressassoc")


def test_asset_powerschool_personemailaddressassoc():
    _test_asset(asset_name="personemailaddressassoc")


def test_asset_powerschool_personphonenumberassoc():
    _test_asset(asset_name="personphonenumberassoc")


def test_asset_powerschool_phonenumber():
    _test_asset(asset_name="phonenumber")


def test_asset_powerschool_prefs():
    _test_asset(asset_name="prefs")


def test_asset_powerschool_roledef():
    _test_asset(asset_name="roledef")


def test_asset_powerschool_schools():
    _test_asset(asset_name="schools")


def test_asset_powerschool_schoolstaff():
    _test_asset(asset_name="schoolstaff")


def test_asset_powerschool_sections():
    _test_asset(asset_name="sections")


def test_asset_powerschool_sectionteacher():
    _test_asset(asset_name="sectionteacher")


def test_asset_powerschool_studentcontactassoc():
    _test_asset(asset_name="studentcontactassoc")


def test_asset_powerschool_studentcontactdetail():
    _test_asset(asset_name="studentcontactdetail")


def test_asset_powerschool_studentcorefields():
    _test_asset(asset_name="studentcorefields")


def test_asset_powerschool_students():
    _test_asset(asset_name="students")


def test_asset_powerschool_teachercategory():
    _test_asset(asset_name="teachercategory")


def test_asset_powerschool_termbins():
    _test_asset(asset_name="termbins")


def test_asset_powerschool_terms():
    _test_asset(asset_name="terms")


def test_asset_powerschool_u_clg_et_stu():
    _test_asset(asset_name="u_clg_et_stu")


def test_asset_powerschool_u_clg_et_stu_alt():
    _test_asset(asset_name="u_clg_et_stu_alt")


def test_asset_powerschool_u_def_ext_students():
    _test_asset(asset_name="u_def_ext_students")


def test_asset_powerschool_u_studentsuserfields():
    _test_asset(asset_name="u_studentsuserfields")


def test_asset_powerschool_users():
    _test_asset(asset_name="users")


def test_asset_powerschool_attendance_code():
    _test_asset(asset_name="attendance_code")


def test_asset_powerschool_attendance_conversion_items():
    _test_asset(asset_name="attendance_conversion_items")


def test_asset_powerschool_bell_schedule():
    _test_asset(asset_name="bell_schedule")


def test_asset_powerschool_calendar_day():
    _test_asset(asset_name="calendar_day")


def test_asset_powerschool_cycle_day():
    _test_asset(asset_name="cycle_day")


def test_asset_powerschool_fte():
    _test_asset(asset_name="fte")


def test_asset_powerschool_gen():
    _test_asset(asset_name="gen")


def test_asset_powerschool_log():
    _test_asset(asset_name="log")


def test_asset_powerschool_period():
    _test_asset(asset_name="period")


def test_asset_powerschool_reenrollments():
    _test_asset(asset_name="reenrollments")


def test_asset_powerschool_spenrollments():
    _test_asset(asset_name="spenrollments")


def test_asset_powerschool_test():
    _test_asset(asset_name="test")


def test_asset_powerschool_testscore():
    _test_asset(asset_name="testscore")


def test_asset_powerschool_attendance():
    _test_asset(
        asset_name="attendance",
        partition_column="transaction_date",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
    )


def test_asset_powerschool_storedgrades():
    _test_asset(
        asset_name="storedgrades",
        partition_column="transaction_date",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
    )


def test_asset_powerschool_assignmentscore():
    _test_asset(
        asset_name="assignmentscore",
        partition_column="whenmodified",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
    )


def test_asset_powerschool_assignmentcategoryassoc():
    _test_asset(
        asset_name="assignmentcategoryassoc",
        partition_column="whenmodified",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
    )


def test_asset_powerschool_assignmentsection():
    _test_asset(
        asset_name="assignmentsection",
        partition_column="whenmodified",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
    )


"""
def test_asset_powerschool_s_nj_crs_x():
    _test_asset(asset_name="s_nj_crs_x")


def test_asset_powerschool_s_nj_ren_x():
    _test_asset(asset_name="s_nj_ren_x")


def test_asset_powerschool_s_nj_stu_x():
    _test_asset(asset_name="s_nj_stu_x")


def test_asset_powerschool_s_nj_usr_x():
    _test_asset(asset_name="s_nj_usr_x")

def test_asset_powerschool_studentrace():
    _test_asset(asset_name="studentrace")

def test_asset_powerschool_pgfinalgrades():
    _test_asset(
        asset_name="pgfinalgrades",
        partition_column="transaction_date",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=pendulum.datetime(year=2016, month=7, day=1),
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S%z",
            end_offset=1,
        ),
    )
"""
