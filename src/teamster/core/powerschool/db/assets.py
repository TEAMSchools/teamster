from datetime import datetime, timedelta

from dagster import DailyPartitionsDefinition, asset
from sqlalchemy import literal_column, select, table, text, union_all

from teamster.core.utils.variables import LOCAL_TIME_ZONE


def construct_sql(context, table_name, columns, where):
    if not where:
        constructed_sql_where = ""
    elif isinstance(where, str):
        constructed_sql_where = where
    elif context.has_partition_key:
        where_column = where["column"]
        partition_start_date = datetime.strptime(
            where["partition_start_date"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )

        start_datetime = context.partition_time_window.start
        end_datetime = start_datetime + timedelta(days=1)

        constructed_sql_where = (
            f"COALESCE( {where_column}, "
            f"TO_TIMESTAMP_TZ( "
            f"'{partition_start_date.isoformat(timespec='microseconds')}' ,"
            " 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM' )"
            " ) >= "
            f"TO_TIMESTAMP_TZ( '{start_datetime.isoformat(timespec='microseconds')}' ,"
            " 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM' )"
            f" AND {where_column}"
            " < "
            f"TO_TIMESTAMP_TZ( '{end_datetime.isoformat(timespec='microseconds')}' , "
            " 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM' )"
        )

        sql = (
            select(*[literal_column(col) for col in columns])
            .select_from(table(table_name))
            .where(text(constructed_sql_where))
        )

        if start_datetime == partition_start_date:
            union_sql = (
                select(*[literal_column(col) for col in columns])
                .select_from(table(table_name))
                .where(text(f"{where_column} IS NULL"))
            )
            sql = union_all(sql, union_sql)

    return sql


def count(context, sql):
    # if sql.whereclause.text == "":
    #     return 1
    # else:
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

    context.log.info(f"Found {count} rows")
    return count


def extract(context, sql, partition_size, output_fmt):
    data = context.resources.ps_db.execute_query(
        query=sql,
        partition_size=partition_size,
        output_fmt=output_fmt,
    )
    return data


def table_asset_factory(asset_name, partition_start_date, columns=["*"], where={}):
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
    )
    def ps_table(context):
        sql = construct_sql(
            context=context, table_name=asset_name, columns=columns, where=where
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
        assets.append(
            table_asset_factory(
                asset_name=table_name, partition_start_date=partition_start_date
            )
        )

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
