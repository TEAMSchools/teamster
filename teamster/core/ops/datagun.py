import gzip
import json
import pathlib

import pandas as pd
from dagster import Dict, In, List, Out, Output, RetryPolicy, Tuple, op

from teamster.core.utils import NOW, TODAY, CustomJSONEncoder, get_last_schedule_run


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


@op(
    ins={"transformed": In(dagster_type=Tuple)},
    tags={"dagster/priority": 4},
    required_resource_keys={"destination", "file_manager"},
    retry_policy=RetryPolicy(max_retries=2),
)
def load_destination(context, transformed):
    dest_config = transformed[0]

    dest_type = dest_config["type"]
    if dest_type == "gsheet":
        file_stem, df_dict = transformed[1:]
        context.resources.destination.update_named_range(
            data=df_dict, spreadsheet_name=file_stem, range_name=file_stem
        )
    elif dest_type == "sftp":
        file_handle = transformed[1]
        dest_path = dest_config.get("path")

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
