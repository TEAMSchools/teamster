from datetime import timedelta

from dagster import asset
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


def table_asset_factory(
    table_name,
    partitions_def=None,
    group_name="powerschool",
    columns=["*"],
    where={},
    partition_size=100000,
    output_fmt="file",
):
    @asset(
        name=table_name,
        partitions_def=partitions_def,
        group_name=group_name,
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
                partition_size=partition_size,
                output_fmt=output_fmt,
            )
        else:
            data = None

        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

        return data
        # TODO: handle output via custom IO mgr, upload list of files to GCS

    return ps_table


# file_manager_key = context.solid_handle.path[0]
# # organize partitions under table folder
# re_match = re.match(r"([\w_]+)_(R\d+)", file_manager_key)
# if re_match:
#     table_name, resync_partition = re_match.groups()
#     file_manager_key = f"{table_name}/{resync_partition}"
# ...
# if data:
#     file_handles = []
#     for i, fp in enumerate(data):
#         if sql.whereclause.text == "":
#             file_stem = f"{file_manager_key}_R{i}"
#         else:
#             file_stem = fp.stem
#         with fp.open(mode="rb") as f:
#             file_handle = context.resources.file_manager.write(
#                 file_obj=f,
#                 key=f"{file_manager_key}/{file_stem}",
#                 ext=fp.suffix[1:],
#             )
#         context.log.info(f"Saved to {file_handle.path_desc}")
#         file_handles.append(file_handle)
