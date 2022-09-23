import re

from dagster import Any, Int, List, Out, Output, op

from teamster.core.utils.functions import get_last_schedule_run
from teamster.core.utils.variables import TODAY


@op(
    config_schema={"sql": Any, "partition_size": Int},
    out={"data": Out(dagster_type=List[Any], is_required=False)},
    required_resource_keys={"db", "ssh", "file_manager"},
    tags={"dagster/priority": 1},
)
def extract(context):
    sql = context.op_config["sql"]
    file_manager_key = context.solid_handle.path[0]

    # format where clause
    sql.whereclause.text = sql.whereclause.text.format(
        today=TODAY.date().isoformat(),
        last_run=get_last_schedule_run(context) or TODAY.isoformat(),
    )

    # parse standard/resync query type
    re_match = re.match(r"([\w_]+)_([RS]\d+)", file_manager_key)
    if re_match is not None:
        table_name, query_type = re_match.groups()
        file_manager_key = f"{table_name}/{query_type}"

        if not context.resources.file_manager.blob_exists(key=file_manager_key):
            context.log.info(f"Running initial sync of {file_manager_key}")
        else:
            # regular run--> skip resync query
            if query_type[0] == "R":
                return Output(value=[], output_name="data")
    else:
        if not context.resources.file_manager.blob_exists(key=file_manager_key):
            # initial run -> drop where clause
            context.log.info(f"Running initial sync of {file_manager_key}")
            sql.whereclause.text = ""

    if context.resources.ssh.tunnel:
        context.log.info("Starting SSH tunnel")
        ssh_tunnel = context.resources.ssh.get_tunnel()
        ssh_tunnel.start()
    else:
        ssh_tunnel = None

    data = context.resources.db.execute_query(
        query=sql, partition_size=context.op_config["partition_size"], output_fmt="file"
    )

    if ssh_tunnel is not None:
        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

    if data:
        file_handles = []
        for fp in data:
            with fp.open(mode="rb") as f:
                file_handle = context.resources.file_manager.write(
                    file_obj=f,
                    key=f"{file_manager_key}/{fp.stem}",
                    ext=fp.suffix[1:],
                )

            context.log.info(f"Saved to {file_handle.path_desc}")
            file_handles.append(file_handle)

        yield Output(value=file_handles, output_name="data")
