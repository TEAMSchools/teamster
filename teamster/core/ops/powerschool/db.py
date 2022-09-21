from dagster import Any, Int, List, Out, Output, String, op

from teamster.core.utils.functions import retry_on_exception


@op(
    config_schema={
        "query": Any,
        "output_fmt": String,
        "partition_size": Int,
        "destination_type": String,
    },
    out={"data": Out(dagster_type=List[Any], is_required=False)},
    required_resource_keys={"db", "ssh", "file_manager"},
    tags={"dagster/priority": 2},
)
@retry_on_exception
def extract(context):
    if context.resources.ssh.tunnel:
        context.log.info("Starting SSH tunnel.")
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
        context.log.info("Stopping SSH tunnel.")
        ssh_tunnel.stop()

    if data:
        if context.op_config["destination_type"] == "file":
            file_handles = []
            for fp in data:
                with fp.open(mode="rb") as f:
                    file_handle = context.resources.file_manager.write(
                        file_obj=f, key=f"{context.job_name}/{fp.stem}", ext=fp.suffix
                    )

                context.log.info(f"Saved to {file_handle.path_desc}.")
                file_handles.append(file_handle)

            yield Output(value=file_handles, output_name="data")
        else:
            yield Output(value=data, output_name="data")
