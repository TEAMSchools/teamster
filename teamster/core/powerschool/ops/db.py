import re

from dagster import Any, Array, In, Int, List, Out, Output, op
from sqlalchemy import text

from teamster.core.utils.functions import get_last_schedule_run
from teamster.core.utils.variables import TODAY


def get_counts_factory(table_names, op_alias):
    @op(
        name=f"get_counts_{op_alias}",
        config_schema={"queries": Array(Any)},
        out={tbl: Out(Any, is_required=False) for tbl in table_names},
        required_resource_keys={"db", "ssh"},
    )
    def get_counts(context):
        context.log.info("Starting SSH tunnel")
        ssh_tunnel = context.resources.ssh.get_tunnel()
        ssh_tunnel.start()

        for sql in context.op_config["queries"]:
            table_name = sql.get_final_froms()[0].name

            # format where clause
            sql.whereclause.text = sql.whereclause.text.format(
                today=TODAY.isoformat(timespec="microseconds"),
                last_run=(get_last_schedule_run(context) or TODAY).isoformat(
                    timespec="microseconds"
                ),
            )

            if sql.whereclause.text == "":
                yield Output(value=sql, output_name=table_name)
            else:
                table_name_clean = re.sub(r"_R\d+$", "", table_name)
                [(count,)] = context.resources.db.execute_query(
                    query=text(
                        (
                            "SELECT COUNT(*) "
                            f"FROM {table_name_clean} "
                            f"WHERE {sql.whereclause.text}"
                        )
                    ),
                    partition_size=1,
                    output_fmt=None,
                )

                if count > 0:
                    yield Output(value=sql, output_name=table_name)

        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

    return get_counts


@op(
    config_schema={"partition_size": Int},
    ins={"sql": In(dagster_type=Any)},
    out={"data": Out(dagster_type=List[Any], is_required=False)},
    required_resource_keys={"db", "ssh", "file_manager"},
    tags={"dagster/priority": 1},
)
def extract_to_data_lake(context, sql):
    file_manager_key = context.solid_handle.path[0]

    # organize partitions under table folder
    re_match = re.match(r"([\w_]+)_(R\d+)", file_manager_key)
    if re_match:
        table_name, resync_partition = re_match.groups()
        file_manager_key = f"{table_name}/{resync_partition}"

    context.log.info("Starting SSH tunnel")
    ssh_tunnel = context.resources.ssh.get_tunnel()
    ssh_tunnel.start()

    data = context.resources.db.execute_query(
        query=sql, partition_size=context.op_config["partition_size"], output_fmt="file"
    )

    context.log.info("Stopping SSH tunnel")
    ssh_tunnel.stop()

    if data:
        file_handles = []
        for i, fp in enumerate(data):
            if sql.whereclause.text == "":
                file_stem = f"{file_manager_key}_R{i}"
            else:
                file_stem = fp.stem

            with fp.open(mode="rb") as f:
                file_handle = context.resources.file_manager.write(
                    file_obj=f,
                    key=f"{file_manager_key}/{file_stem}",
                    ext=fp.suffix[1:],
                )

            context.log.info(f"Saved to {file_handle.path_desc}")
            file_handles.append(file_handle)

        yield Output(value=file_handles, output_name="data")
