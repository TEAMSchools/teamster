from datetime import datetime, timedelta

from dagster import DailyPartitionsDefinition, asset
from sqlalchemy import literal_column, select, table, text

from teamster.core.utils.variables import LOCAL_TIME_ZONE


def construct_sql(context, table_name, columns, where):
    if not where:
        constructed_where = ""
    elif isinstance(where, str):
        constructed_where = where
    elif context.has_partition_key:
        where_column = where["column"]
        partition_start_date = datetime.strptime(
            where["partition_start_date"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )

        start_datetime = context.partition_time_window.start
        end_datetime = start_datetime + timedelta(days=1)

        if start_datetime == partition_start_date:
            constructed_where = (
                f"{where_column} < TO_TIMESTAMP_TZ('"
                f"{end_datetime.isoformat(timespec='microseconds')}"
                "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM') OR "
                f"{where_column} IS NULL"
            )
        else:
            constructed_where = (
                f"{where_column} >= TO_TIMESTAMP_TZ('"
                f"{start_datetime.isoformat(timespec='microseconds')}"
                "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM') AND "
                f"{where_column} < TO_TIMESTAMP_TZ('"
                f"{end_datetime.isoformat(timespec='microseconds')}"
                "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')"
            )
    else:
        constructed_where = ""

    return (
        select(*[literal_column(col) for col in columns])
        .select_from(table(table_name))
        .where(text(constructed_where))
    )


def count(context, sql):
    if sql.whereclause.text != "":
        query = text(
            (
                "SELECT COUNT(*) "
                f"FROM {sql.get_final_froms()[0].name} "
                f"WHERE {sql.whereclause.text}"
            )
        )
    else:
        query = text("SELECT COUNT(*) " f"FROM {sql.get_final_froms()[0].name}")

    [(count,)] = context.resources.ps_db.execute_query(
        query=query,
        partition_size=1,
        output=None,
    )
    context.log.info(f"Found {count} rows")

    return count


def extract(context, sql, partition_size, output):
    data = context.resources.ps_db.execute_query(
        query=sql,
        partition_size=partition_size,
        output=output,
    )
    return data


def table_asset_factory(asset_name, partition_start_date=None, columns=["*"], where={}):
    if partition_start_date is not None:
        where["partition_start_date"] = partition_start_date
        daily_partitions_def = DailyPartitionsDefinition(
            start_date=partition_start_date,
            timezone=str(LOCAL_TIME_ZONE),
            fmt="%Y-%m-%dT%H:%M:%S.%f%z",
        )
    else:
        daily_partitions_def = None

    @asset(
        name=asset_name,
        partitions_def=daily_partitions_def,
        required_resource_keys={"ps_db", "ps_ssh"},
        output_required=False,
        io_manager_key="ps_io",
    )
    def ps_table(context):
        sql = construct_sql(
            context=context, table_name=asset_name, columns=columns, where=where
        )

        ssh_tunnel = context.resources.ps_ssh.get_tunnel()

        context.log.info("Starting SSH tunnel")
        ssh_tunnel.start()

        row_count = count(context=context, sql=sql)
        if row_count > 0:
            data = extract(
                context=context,
                sql=sql,
                partition_size=100000,
                output="avro",
            )
        else:
            data = None

        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

        return data

    return ps_table


def generate_powerschool_assets(partition_start_date=None):
    assets = []

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
        assets.append(table_asset_factory(asset_name=table_name))

    # table-specific partition
    assets.append(
        table_asset_factory(
            asset_name="log",
            where={"column": "entry_date"},
            partition_start_date=partition_start_date,
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
        assets.append(
            table_asset_factory(
                asset_name=table_name,
                where={"column": "transaction_date"},
                partition_start_date=partition_start_date,
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
        assets.append(
            table_asset_factory(
                asset_name=table_name,
                where={"column": "whenmodified"},
                partition_start_date=partition_start_date,
            )
        )

    return assets
