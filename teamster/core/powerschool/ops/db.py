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

    # organize partitions under table folder
    re_match = re.match(r"([\w_]+)_(R\d+)", file_manager_key)
    if re_match:
        table_name, resync_partition = re_match.groups()
        file_manager_key = f"{table_name}/{resync_partition}"

    # format where clause
    sql.whereclause.text = sql.whereclause.text.format(
        today=TODAY.isoformat(),
        last_run=get_last_schedule_run(context) or TODAY.isoformat(),
    )

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
