import gzip
import json
import pathlib
import re

import pandas as pd
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
from teamster.core.utils import NOW, TODAY, CustomJSONEncoder, get_last_schedule_run


@op(
    config_schema=QUERY_CONFIG,
    out={"dynamic_query": DynamicOut(dagster_type=Tuple)},
    tags={"dagster/priority": 1},
)
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
                today=TODAY, last_run=get_last_schedule_run(context=context)
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

    # TODO: refactor query_kwargs to config
    query_kwargs = {}
    if dest_config["type"] == "fs":
        query_kwargs["output_fmt"] = "files"

    data = context.resources.db.execute_query(query, **query_kwargs)

    if ssh_tunnel is not None:
        context.log.info("Stopping SSH tunnel.")
        ssh_tunnel.stop()

    if data:
        if query_kwargs["output_fmt"] == "files":
            file_handles = []
            for fp in data:
                with fp.open(mode="rb") as f:
                    file_handle = context.resources.file_manager.write(
                        file_obj=f, key=f"{table_name}/{fp.stem}", ext=fp.suffix
                    )
                file_handles.append(file_handle)

            yield Output(value=file_handles, output_name="data")
        else:
            yield Output(value=file_config, output_name="file_config")
            yield Output(value=dest_config, output_name="dest_config")
            yield Output(value=data, output_name="data")


@op(
    ins={
        "data": In(dagster_type=List[Dict]),
        "file_config": In(dagster_type=Dict),
        "dest_config": In(dagster_type=Dict),
    },
    out={"transformed": Out(dagster_type=Tuple, is_required=False)},
    required_resource_keys={"file_manager"},
    tags={"dagster/priority": 3},
)
def transform(context, data, file_config, dest_config):
    mapping_key = context.get_mapping_key()
    table_name = mapping_key[: mapping_key.rfind("_")]

    now_ts = NOW.timestamp()
    if file_config:
        file_stem = file_config["stem"].format(
            today=TODAY.date().isoformat(),
            now=now_ts.replace(".", "_"),
            last_run=get_last_schedule_run(context=context),
        )
        file_suffix = file_config["suffix"]
        file_format = file_config.get("format", {})

        file_encoding = file_format.get("encoding", "utf-8")
    else:
        file_stem = now_ts.replace(".", "_")
        file_suffix = "json.gz"
        file_format = {}
        file_encoding = "utf-8"

    dest_type = dest_config["type"]

    if dest_type == "gsheet":
        context.log.info("Transforming data to DataFrame")
        df = pd.DataFrame(data=data)
        df_json = df.to_json(orient="split", date_format="iso", index=False)

        df_dict = json.loads(df_json)
        df_dict["shape"] = df.shape

        yield Output(value=(dest_config, file_stem, df_dict), output_name="transformed")
    elif dest_type in ["fs", "sftp"]:
        context.log.info(f"Transforming data to {file_suffix}")

        if file_suffix == "json":
            data_bytes = json.dumps(obj=data, cls=CustomJSONEncoder).encode(
                file_encoding
            )
        elif file_suffix == "json.gz":
            data_bytes = gzip.compress(
                json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
            )
        elif file_suffix in ["csv", "txt", "tsv"]:
            df = pd.DataFrame(data=data)
            data_bytes = df.to_csv(index=False, **file_format).encode(file_encoding)

        file_handle = context.resources.file_manager.write_data(
            data=data_bytes,
            key=f"{(dest_config.get('name') or table_name or 'data')}/{file_stem}",
            ext=file_suffix,
        )
        context.log.info(f"Saved to {file_handle.path_desc}.")

        if dest_type == "sftp":
            yield Output(value=(dest_config, file_handle), output_name="transformed")
