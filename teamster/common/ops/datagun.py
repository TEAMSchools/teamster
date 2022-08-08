import gzip
import json
import pathlib
import re

import pandas as pd
from dagster import (
    Dict,
    DynamicOut,
    DynamicOutput,
    In,
    List,
    Out,
    Output,
    RetryPolicy,
    Tuple,
    op,
)

from teamster.common.config.datagun import COMPOSE_QUERIES_CONFIG
from teamster.common.utils import CustomJSONEncoder, TODAY


@op(
    config_schema=COMPOSE_QUERIES_CONFIG,
    out={"dynamic_query": DynamicOut(dagster_type=Tuple)},
    tags={"dagster/priority": 1},
)
def compose_queries(context):
    dest_config = context.op_config["destination"]
    queries = context.op_config["queries"]

    for i, q in enumerate(queries):
        file_config = q["file"]
        file_stem = re.sub(r"[^A-Za-z0-9_]+", "", file_config["stem"])
        [(query_type, value)] = q["sql"].items()

        if query_type == "text":
            query = value
        elif query_type == "file":
            with pathlib.Path(value).absolute().open() as f:
                query = f.read()
        elif query_type == "schema":
            where = value.get("where")
            query = " ".join(
                [
                    f"SELECT {value['columns']}",
                    f"FROM {value['table']}",
                    f"WHERE {where};" if where else ";",
                ]
            )

        yield DynamicOutput(
            value=(query, file_config, dest_config),
            output_name="dynamic_query",
            mapping_key=(f"{query_type}_{file_stem}_{file_config['suffix']}_{i}"),
        )


@op(
    ins={"dynamic_query": In(dagster_type=Tuple)},
    out={
        "data": Out(dagster_type=List[Dict], is_required=False),
        "file_config": Out(dagster_type=Dict, is_required=False),
        "dest_config": Out(dagster_type=Dict, is_required=False),
    },
    required_resource_keys={"db"},
    tags={"dagster/priority": 2},
)
def extract(context, dynamic_query):
    query, file_config, dest_config = dynamic_query

    data = context.resources.db.execute_text_query(query)
    if data:
        yield Output(value=data, output_name="data")
        yield Output(value=file_config, output_name="file_config")
        yield Output(value=dest_config, output_name="dest_config")


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
    file_stem = file_config["stem"].format(TODAY.date().isoformat())
    file_suffix = file_config["suffix"]
    file_format = file_config.get("format", {})
    file_encoding = file_format.get("encoding", "utf-8")

    dest_name = dest_config["name"]
    dest_type = dest_config["type"]
    dest_path = dest_config.get("path")

    context.log.info(f"Transforming data to {file_suffix}")
    if file_suffix == "gsheet":
        df = pd.DataFrame(data=data)
        df_json = df.to_json(orient="split", date_format="iso", index=False)
        df_dict = json.loads(df_json)
        df_dict["shape"] = df.shape
    elif file_suffix == "json.gz":
        data_bytes = gzip.compress(
            json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
        )
    elif file_suffix == "json":
        data_bytes = json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
    elif file_suffix in ["csv", "txt", "tsv"]:
        df = pd.DataFrame(data=data)
        data_bytes = df.to_csv(index=False, **file_format).encode(file_encoding)

    if dest_type == "gsheet":
        yield Output(value=(dest_type, (df_dict, file_stem)), output_name="transformed")
    elif dest_type == "sftp":
        file_handle = context.resources.file_manager.upload_from_string(
            obj=data_bytes,
            file_key=f"{dest_name}/{file_stem}.{file_suffix}",
        )
        context.log.info(f"Saved to {file_handle.path_desc}.")

        yield Output(
            value=(dest_type, (file_handle, dest_path)), output_name="transformed"
        )


@op(
    ins={"transformed": In(dagster_type=Tuple)},
    tags={"dagster/priority": 4},
    required_resource_keys={"destination", "file_manager"},
    retry_policy=RetryPolicy(max_retries=2),
)
def load_destination(context, transformed):
    dest_type, transformed_ins = transformed

    if dest_type == "gsheet":
        data, file_stem = transformed_ins
        context.resources.destination.update_named_range(
            data=data, spreadsheet_name=file_stem, range_name=file_stem
        )
    elif dest_type == "sftp":
        file_handle, dest_path = transformed_ins

        sftp_conn = context.resources.destination.get_connection()
        file_name = pathlib.Path(file_handle.gcs_key).name

        with sftp_conn.open_sftp() as sftp:
            sftp.chdir(".")

            if dest_path:
                dest_filepath = pathlib.Path(sftp.getcwd()) / dest_path / file_name
            else:
                dest_filepath = pathlib.Path(sftp.getcwd()) / file_name

            # confirm dest_filepath dir exists or create it
            try:
                sftp.stat(str(dest_filepath.parent))
            except IOError:
                dir_path = pathlib.Path("/")
                for dir in dest_filepath.parent.parts:
                    dir_path = dir_path / dir
                    try:
                        sftp.stat(str(dir_path))
                    except IOError:
                        context.log.info(f"Creating directory: {dir_path}")
                        sftp.mkdir(str(dir_path))

            # if dest_path given, chdir after confirming
            if dest_path:
                sftp.chdir(str(dest_filepath.parent))

            context.log.info(
                (
                    "Starting to transfer file from "
                    f"{file_handle.path_desc} to {dest_filepath}"
                )
            )

            with sftp.file(file_name, "w") as f:
                f.write(
                    context.resources.file_manager.download_as_bytes(
                        file_handle=file_handle
                    )
                )
