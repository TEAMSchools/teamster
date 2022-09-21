from dagster import Any, Int, List, Out, Output, String, op

from teamster.core.utils.functions import get_last_schedule_run
from teamster.core.utils.variables import TODAY


@op(
    config_schema={
        "query": Any,
        "output_fmt": String,
        "partition_size": Int,
        "destination_type": String,
    },
    out={"data": Out(dagster_type=List[Any], is_required=False)},
    required_resource_keys={"db", "ssh", "file_manager"},
    # tags={"dagster/priority": 2},
)
def extract(context):
    file_manager_key = context.solid_handle.path[0]

    if context.op_config[
        "destination_type"
    ] == "file" and not context.resources.file_manager.blob_exists(
        key=file_manager_key + "/"
    ):
        context.log.info(f"Running initial sync of {file_manager_key}")
        context.op_config["query"].whereclause.text = ""
    else:
        context.op_config["query"].whereclause.text.format(
            today=TODAY.date().isoformat(),
            last_run=get_last_schedule_run(context) or TODAY.isoformat(),
        )

    if context.resources.ssh.tunnel:
        context.log.info("Starting SSH tunnel")
        ssh_tunnel = context.resources.ssh.get_tunnel()
        ssh_tunnel.start()
    else:
        ssh_tunnel = None

    data = context.resources.db.execute_query(
        query=context.op_config["query"],
        partition_size=context.op_config["partition_size"],
        output_fmt=context.op_config["output_fmt"],
    )

    if ssh_tunnel is not None:
        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

    if data:
        if context.op_config["destination_type"] == "file":
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
        else:
            yield Output(value=data, output_name="data")
