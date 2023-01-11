import os
from datetime import timedelta

from dagster import HourlyPartitionsDefinition, asset
from sqlalchemy import literal_column, select, table, text


def construct_sql(context, table_name, columns, where):
    if not where:
        constructed_sql_where = ""
    elif isinstance(where, str):
        constructed_sql_where = where
    elif context.has_partition_key:
        where_column = where["column"]
        start_datetime = context.partition_time_window.start
        end_datetime = start_datetime + timedelta(hours=1)

        constructed_sql_where = (
            f"{where_column} >= TO_TIMESTAMP_TZ('"
            f"{start_datetime.isoformat(timespec='microseconds')}"
            "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM') AND "
            f"{where_column} < TO_TIMESTAMP_TZ('"
            f"{end_datetime.isoformat(timespec='microseconds')}"
            "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')"
        )

    return (
        select(*[literal_column(col) for col in columns])
        .select_from(table(table_name))
        .where(text(constructed_sql_where))
    )


def count(context, sql):
    if sql.whereclause.text == "":
        return 1
    else:
        [(count,)] = context.resources.ps_db.execute_query(
            query=text(
                (
                    "SELECT COUNT(*) "
                    f"FROM {sql.get_final_froms()[0].name} "
                    f"WHERE {sql.whereclause.text}"
                )
            ),
            partition_size=1,
            output_fmt=None,
        )
        return count


def extract(context, sql, partition_size, output_fmt):
    data = context.resources.ps_db.execute_query(
        query=sql,
        partition_size=partition_size,
        output_fmt=output_fmt,
    )
    return data


def table_asset_factory(asset_name, partitions_def=None, columns=["*"], where={}):
    @asset(
        name=asset_name,
        partitions_def=partitions_def,
        required_resource_keys={"ps_db", "ps_ssh"},
        output_required=False,
    )
    def ps_table(context):
        sql = construct_sql(
            context=context, table_name=table_name, columns=columns, where=where
        )

        context.log.info("Starting SSH tunnel")
        ssh_tunnel = context.resources.ps_ssh.get_tunnel()
        ssh_tunnel.start()

        row_count = count(context=context, sql=sql)
        if row_count > 0:
            data = extract(
                context=context,
                sql=sql,
                partition_size=100000,
                output_fmt="dict",
            )
        else:
            data = None

        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

        return data

    return ps_table


hourly_partition = HourlyPartitionsDefinition(
    start_date="2002-07-01T00:00:00.000000-0400",
    timezone=os.getenv("LOCAL_TIME_ZONE"),
    fmt="%Y-%m-%dT%H:%M:%S.%f%z",
)

core_ps_db_assets = []

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
    core_ps_db_assets.append(table_asset_factory(asset_name=table_name))

# table-specific partition
core_ps_db_assets.append(
    table_asset_factory(
        asset_name="log",
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
    core_ps_db_assets.append(
        table_asset_factory(
            asset_name=table_name,
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
    core_ps_db_assets.append(
        table_asset_factory(
            asset_name=table_name,
            where={"column": "whenmodified"},
            partitions_def=hourly_partition,
        )
    )
