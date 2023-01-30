import os
from pathlib import Path

import pendulum
from dagster import AssetsDefinition, HourlyPartitionsDefinition, Output, asset
from sqlalchemy import literal_column, select, table, text

from teamster.core.utils.variables import LOCAL_TIME_ZONE


def construct_sql(context, table_name, columns, where_column, partition_start_date):
    if partition_start_date is not None:
        window_start = context.partition_time_window.start
        window_end = window_start.add(hours=1)

        if context.partition_time_window.start == pendulum.parse(
            text=partition_start_date, tz=LOCAL_TIME_ZONE.name
        ):
            constructed_where = (
                f"{where_column} < TO_TIMESTAMP('"
                f"{window_end.format('YYYY-MM-DDTHH:mm:ss.SSSSSS')}"
                "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') OR "
                f"{where_column} IS NULL"
            )
        else:
            constructed_where = (
                f"{where_column} >= TO_TIMESTAMP('"
                f"{window_start.format('YYYY-MM-DDTHH:mm:ss.SSSSSS')}"
                "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
                f"{where_column} < TO_TIMESTAMP('"
                f"{window_end.format('YYYY-MM-DDTHH:mm:ss.SSSSSS')}"
                "', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            )
    else:
        constructed_where = ""

    return (
        select(*[literal_column(col) for col in columns])
        .select_from(table(table_name))
        .where(text(constructed_where))
    )


def count(context, sql) -> int:
    query_text = f"SELECT COUNT(*) FROM {sql.get_final_froms()[0].name}"

    if sql.whereclause.text == "":
        query = text(query_text)
    else:
        query = text(f"{query_text} WHERE {sql.whereclause.text}")

    [(count,)] = context.resources.ps_db.execute_query(
        query=query,
        partition_size=1,
        output=None,
    )

    return count


def build_powerschool_table_asset(
    asset_name,
    code_location,
    partition_start_date=None,
    columns=["*"],
    where_column="",
) -> AssetsDefinition:
    if partition_start_date is not None:
        hourly_partitions_def = HourlyPartitionsDefinition(
            start_date=partition_start_date,
            timezone=LOCAL_TIME_ZONE.name,
            fmt="%Y-%m-%dT%H:%M:%S.%f",
        )
    else:
        hourly_partitions_def = None

    @asset(
        name=asset_name,
        key_prefix=["powerschool", code_location],
        partitions_def=hourly_partitions_def,
        io_manager_key="ps_io",
        required_resource_keys={"ps_db", "ps_ssh"},
    )
    def _asset(context) -> Path:
        sql = construct_sql(
            context=context,
            table_name=asset_name,
            columns=columns,
            where_column=where_column,
            partition_start_date=partition_start_date,
        )

        ssh_tunnel = context.resources.ps_ssh.get_tunnel(
            remote_port=1521,
            remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST"),
            local_port=1521,
        )

        try:
            context.log.info("Starting SSH tunnel")
            ssh_tunnel.start()

            row_count = count(context=context, sql=sql)
            context.log.info(f"Found {row_count} rows")

            filename: Path = context.resources.ps_db.execute_query(
                query=sql, partition_size=100000, output="avro"
            )
        finally:
            context.log.info("Stopping SSH tunnel")
            ssh_tunnel.stop()

        return Output(value=filename, metadata={"records": row_count})

    return _asset
