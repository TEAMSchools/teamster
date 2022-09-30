import gzip
import json
import pathlib

import pandas as pd
from dagster import Any, Dict, In, Int, List, Out, Output, Permissive, String, op

from teamster.core.utils.classes import CustomJSONEncoder
from teamster.core.utils.functions import get_last_schedule_run
from teamster.core.utils.variables import NOW, TODAY


@op(
    config_schema={"sql": Any, "partition_size": Int, "output_fmt": String},
    out={"data": Out(dagster_type=List[Dict], is_required=False)},
    required_resource_keys={"db"},
    tags={"dagster/priority": 1},
)
def extract(context):
    sql = context.op_config["sql"]

    # format where clause
    if hasattr(sql, "whereclause"):
        sql.whereclause.text = sql.whereclause.text.format(
            today=TODAY.isoformat(),
            last_run=get_last_schedule_run(context) or TODAY.isoformat(),
        )

    data = context.resources.db.execute_query(
        query=sql,
        partition_size=context.op_config["partition_size"],
        output_fmt=context.op_config["output_fmt"],
    )

    if data:
        yield Output(value=data, output_name="data")


@op(
    config_schema={
        "destination_type": String,
        "destination_name": String,
        "file": Permissive(),
    },
    ins={"data": In(dagster_type=List[Dict])},
    out={
        "file_handle": Out(dagster_type=Any, is_required=False),
        "df_dict": Out(dagster_type=Any, is_required=False),
    },
    required_resource_keys={"file_manager"},
    tags={"dagster/priority": 2},
)
def transform(context, data):
    file_config = context.op_config["file"]
    destination_type = context.op_config["destination_type"]
    destination_name = context.op_config["destination_name"]

    file_suffix = file_config["suffix"]
    file_encoding = file_config["encoding"]
    file_stem = file_config["stem"].format(
        today=TODAY.date().isoformat(),
        now=str(NOW.timestamp()).replace(".", "_"),
        last_run=get_last_schedule_run(context=context) or TODAY.date().isoformat(),
    )

    if destination_type == "gsheet":
        context.log.info("Transforming data to DataFrame")
        df = pd.DataFrame(data=data)
        df_json = df.to_json(orient="split", date_format="iso", index=False)

        df_dict = json.loads(df_json)
        df_dict["shape"] = df.shape

        yield Output(value=df_dict, output_name="df_dict")
    elif destination_type in ["fs", "sftp"]:
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
            data_bytes = df.to_csv(index=False, **file_config["format"]).encode(
                file_encoding
            )

        file_handle = context.resources.file_manager.write_data(
            data=data_bytes,
            key=f"{destination_name}/{file_stem}",
            ext=file_suffix,
        )
        context.log.info(f"Saved to {file_handle.path_desc}.")

        if destination_type == "sftp":
            yield Output(value=file_handle, output_name="file_handle")


@op(
    config_schema={"destination_path": String},
    ins={"file_handle": In(dagster_type=Any)},
    tags={"dagster/priority": 3},
    required_resource_keys={"sftp", "file_manager"},
)
def load_sftp(context, file_handle):
    destination_path = context.op_config["destination_path"]
    sftp_conn = context.resources.sftp.get_connection()

    file_name = pathlib.Path(file_handle.gcs_key).name

    with sftp_conn.open_sftp() as sftp:
        sftp.chdir(".")

        if destination_path != "":
            destination_filepath = (
                pathlib.Path(sftp.getcwd()) / destination_path / file_name
            )
        else:
            destination_filepath = pathlib.Path(sftp.getcwd()) / file_name

        # confirm destination_filepath dir exists or create it
        try:
            sftp.stat(str(destination_filepath.parent))
        except IOError:
            dir_path = pathlib.Path("/")
            for dir in destination_filepath.parent.parts:
                dir_path = dir_path / dir
                try:
                    sftp.stat(str(dir_path))
                except IOError:
                    context.log.info(f"Creating directory: {dir_path}")
                    sftp.mkdir(str(dir_path))

        # if destination_path given, chdir after confirming
        if destination_path:
            sftp.chdir(str(destination_filepath.parent))

        context.log.info(
            (
                "Starting to transfer file from "
                f"{file_handle.path_desc} to {destination_filepath}"
            )
        )

        with sftp.file(file_name, "w") as f:
            f.write(
                context.resources.file_manager.download_as_bytes(
                    file_handle=file_handle
                )
            )


@op(
    ins={"df_dict": In(dagster_type=Any)},
    tags={"dagster/priority": 3},
    required_resource_keys={"gsheet"},
)
def load_gsheet(context, df_dict):
    file_stem = context.op_config["file_stem"].format(
        now=str(NOW.timestamp()).replace(".", "_")
    )

    if file_stem[0].isnumeric():
        file_stem = "GS" + file_stem

    context.resources.gsheet.update_named_range(
        data=df_dict, spreadsheet_name=file_stem, range_name=file_stem
    )
