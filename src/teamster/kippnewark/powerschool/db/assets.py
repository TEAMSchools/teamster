from dagster import HourlyPartitionsDefinition

from teamster.core.powerschool.db.assets import table_asset_factory

hourly_partition = HourlyPartitionsDefinition(
    start_date="2002-07-01T00:00:00.000000-0400",
    timezone="US/Eastern",
    fmt="%Y-%m-%dT%H:%M:%S.%f%z",
)

ps_db_assets = []

# not partitionable
for table_name in [
    "attendance_conversion_items",
    "gen",
    "test",
    "testscore",
    "attendance_code",
    "bell_schedule",
    "cycle_day",
    "fte",
    "period",
    "reenrollments",
    "calendar_day",
    "spenrollments",
]:
    ps_db_assets.append(table_asset_factory(table_name=table_name))

# table-specific partition
ps_db_assets.append(
    table_asset_factory(
        table_name="log",
        where={"column": "entry_date"},
        partitions_def=hourly_partition,
    )
)

# transaction_date
for table_name in [
    "attendance",
    "cc",
    "courses",
    "pgfinalgrades",
    "prefs",
    "schools",
    "sections",
    "storedgrades",
    "students",
    "termbins",
    "terms",
]:
    ps_db_assets.append(
        table_asset_factory(
            table_name=table_name,
            where={"column": "transaction_date"},
            partitions_def=hourly_partition,
        )
    )

# whenmodified
for table_name in [
    "assignmentcategoryassoc",
    "assignmentscore",
    "assignmentsection",
    "codeset",
    "districtteachercategory",
    "emailaddress",
    "gradecalcformulaweight",
    "gradecalcschoolassoc",
    "gradecalculationtype",
    "gradeformulaset",
    "gradescaleitem",
    "gradeschoolconfig",
    "gradeschoolformulaassoc",
    "gradesectionconfig",
    "originalcontactmap",
    "person",
    "personaddress",
    "personaddressassoc",
    "personemailaddressassoc",
    "personphonenumberassoc",
    "phonenumber",
    "roledef",
    "schoolstaff",
    "sectionteacher",
    "studentcontactassoc",
    "studentcontactdetail",
    "studentcorefields",
    "studentrace",
    "teachercategory",
    "users",
]:
    ps_db_assets.append(
        table_asset_factory(
            table_name=table_name,
            where={"column": "whenmodified"},
            partitions_def=hourly_partition,
        )
    )
