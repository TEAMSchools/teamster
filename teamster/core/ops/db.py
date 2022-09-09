import pathlib
import re

from dagster import (
    Any,
    Dict,
    DynamicOut,
    DynamicOutput,
    In,
    List,
    Out,
    Output,
    Tuple,
    op,
)
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.db.schema import QUERY_CONFIG, SSH_TUNNEL_CONFIG
from teamster.core.utils.functions import get_last_schedule_run, retry_on_exception
from teamster.core.utils.variables import TODAY


@op(
    config_schema=QUERY_CONFIG,
    out={"dynamic_query": DynamicOut(dagster_type=Tuple)},
    tags={"dagster/priority": 1},
)
@retry_on_exception
def compose_queries(context):
    dest_config = context.op_config["destination"]
    queries = context.op_config["queries"]

    for i, q in enumerate(queries):
        [(query_type, value)] = q["sql"].items()

        if query_type == "text":
            table_name = "query"
            query = text(value)
        elif query_type == "file":
            query_file = pathlib.Path(value).absolute()
            table_name = query_file.stem
            with query_file.open(mode="r") as f:
                query = text(f.read())
        elif query_type == "schema":
            table_name = value["table"]["name"]
            where_fmt = value.get("where", "").format(
                today=TODAY.date().isoformat(),
                last_run=get_last_schedule_run(context=context)
                or TODAY.date().isoformat(),
            )
            query = (
                select(*[literal_column(col) for col in value["select"]])
                .select_from(table(**value["table"]))
                .where(text(where_fmt))
            )

        yield DynamicOutput(
            value=(query, q.get("file", {}), dest_config),
            output_name="dynamic_query",
            mapping_key=re.sub(
                r"[^A-Za-z0-9_]+",
                "",
                f"{(q.get('file', {}).get('stem') or table_name)}_{i}",
            ),
        )


@op(
    config_schema=SSH_TUNNEL_CONFIG,
    ins={"dynamic_query": In(dagster_type=Tuple)},
    out={
        "data": Out(dagster_type=List[Any], is_required=False),
        "file_config": Out(dagster_type=Dict, is_required=False),
        "dest_config": Out(dagster_type=Dict, is_required=False),
    },
    required_resource_keys={"db", "ssh", "file_manager"},
    tags={"dagster/priority": 2},
)
@retry_on_exception
def extract(context, dynamic_query):
    mapping_key = context.get_mapping_key()
    table_name = mapping_key[: mapping_key.rfind("_")]

    query, file_config, dest_config = dynamic_query

    if hasattr(context.resources.ssh, "get_tunnel"):
        context.log.info("Starting SSH tunnel.")
        ssh_tunnel = context.resources.ssh.get_tunnel(**context.op_config)
        ssh_tunnel.start()
    else:
        ssh_tunnel = None

    if dest_config["type"] == "fs":
        data = context.resources.db.execute_query(query, output_fmt="files")
    else:
        data = context.resources.db.execute_query(query)

    if ssh_tunnel is not None:
        context.log.info("Stopping SSH tunnel.")
        ssh_tunnel.stop()

    if data:
        if dest_config["type"] == "fs":
            file_handles = []
            for fp in data:
                with fp.open(mode="rb") as f:
                    file_handle = context.resources.file_manager.write(
                        file_obj=f, key=f"{table_name}/{fp.stem}", ext=fp.suffix
                    )

                context.log.info(f"Saved to {file_handle.path_desc}.")
                file_handles.append(file_handle)

            yield Output(value=file_handles, output_name="data")
        else:
            yield Output(value=file_config, output_name="file_config")
            yield Output(value=dest_config, output_name="dest_config")
            yield Output(value=data, output_name="data")
