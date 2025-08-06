import gc
import gzip
import json
import pathlib
import re
from csv import DictWriter
from datetime import datetime
from io import StringIO

from dagster import (
    AssetExecutionContext,
    AssetKey,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    asset,
)
from dagster_shared import check
from google.cloud.bigquery import Client
from google.cloud.storage import Blob
from sqlalchemy.sql.expression import literal_column, select, table, text

from teamster.core.utils.classes import CustomJSONEncoder
from teamster.libraries.ssh.resources import SSHResource


def format_file_name(stem: str, suffix: str, **substitutions):
    return f"{stem.format(**substitutions)}.{suffix}"


def construct_query(query_type, query_value) -> str:
    if query_type == "text":
        return query_value
    elif query_type == "file":
        sql_file = pathlib.Path(query_value).absolute()
        return sql_file.read_text()
    elif query_type == "schema":
        return str(
            select(
                *[literal_column(text=col) for col in query_value.get("select", ["*"])]
            )
            .select_from(table(**query_value["table"]))
            .where(*[text(w) for w in query_value.get("where", "")])
        )
    else:
        raise


def transform_data(
    data: list[dict],
    file_suffix: str,
    file_encoding: str = "utf-8",
    file_format: dict | None = None,
):
    if file_format is None:
        file_format = {}

    if file_suffix == "json":
        transformed_data = json.dumps(obj=data, cls=CustomJSONEncoder).encode(
            file_encoding
        )
    elif file_suffix == "json.gz":
        transformed_data = gzip.compress(
            json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
        )
    elif file_suffix in ["csv", "txt", "tsv"]:
        field_names = data[0].keys()
        write_header = file_format.pop("header", True)
        header_replacements = file_format.pop("header_replacements", {})

        f = StringIO()

        dict_writer = DictWriter(f=f, fieldnames=field_names, **file_format)

        if not write_header:
            pass
        elif header_replacements:
            dict_writer.writerow(
                {k: header_replacements.get(k, k) for k in field_names}
            )
        else:
            dict_writer.writeheader()

        dict_writer.writerows(data)

        transformed_data = f.getvalue().encode(file_encoding)

        f.close()
    else:
        raise Exception(f"Invalid {file_suffix=}")

    del data
    gc.collect()

    return transformed_data


def load_sftp(
    context: AssetExecutionContext,
    ssh: SSHResource,
    data,
    file_name: str,
    destination_path: str,
):
    with ssh.get_connection().open_sftp() as sftp:
        check.not_none(value=sftp.get_channel()).settimeout(ssh.timeout)

        sftp.chdir(".")

        cwd_path = pathlib.Path(str(sftp.getcwd()))

        if destination_path != "":
            destination_filepath = cwd_path / destination_path / file_name
        else:
            destination_filepath = cwd_path / file_name

        context.log.debug(destination_filepath)

        # confirm destination_filepath dir exists or create it
        if str(destination_filepath.parent) != "/":
            try:
                sftp.stat(str(destination_filepath.parent))
            except IOError:
                path = pathlib.Path("/")

                for part in destination_filepath.parent.parts:
                    path = path / part

                    try:
                        sftp.stat(str(path))
                    except IOError:
                        context.log.info(f"Creating directory: {path}")
                        sftp.mkdir(path=str(path))

        if isinstance(data, Blob):
            context.log.info(f"Saving file to {destination_filepath}")
            with sftp.open(filename=str(destination_filepath), mode="w") as file_obj:
                data.download_to_file(file_obj=file_obj)
        else:
            # if destination_path given, chdir after confirming
            if destination_path:
                context.log.info(f"Changing directory to {destination_filepath.parent}")
                sftp.chdir(str(destination_filepath.parent))

            context.log.info(f"Saving file to {destination_filepath}")
            with sftp.file(filename=file_name, mode="w") as sftp_file:
                sftp_file.write(data)


def build_bigquery_query_sftp_asset(
    code_location,
    timezone,
    query_config,
    file_config,
    destination_config,
    op_tags: dict[str, str] | None = None,
    partitions_def=None,
):
    query_type = query_config["type"]
    query_value = query_config["value"]

    file_suffix = file_config["suffix"]
    file_stem = file_config["stem"]
    file_encoding = file_config.get("encoding", "utf-8")
    file_format = file_config.get("format", {})

    destination_name = destination_config["name"]
    destination_path = destination_config.get("path", "")

    asset_name = re.sub(pattern=r"\W", repl="", string=f"{file_stem}_{file_suffix}")

    @asset(
        key=[code_location, "extracts", destination_name, asset_name],
        deps=[
            AssetKey(
                [
                    code_location,
                    "extracts",
                    destination_name,
                    query_value["table"]["name"],
                ]
            )
        ],
        metadata={**query_config, **file_config},
        required_resource_keys={"gcs", "db_bigquery", f"ssh_{destination_name}"},
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="extracts",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext):
        now = datetime.now(timezone)

        if context.has_partition_key and isinstance(
            context.assets_def.partitions_def, MultiPartitionsDefinition
        ):
            partition_key = check.inst(
                obj=context.partition_key, ttype=MultiPartitionKey
            )

            substitutions = partition_key.keys_by_dimension
            query_value["where"] = [
                f"_dagster_partition_{k.dimension_name} = '{k.partition_key}'"
                for k in partition_key.dimension_keys
            ]
        else:
            substitutions = {
                "now": str(now.timestamp()).replace(".", "_"),
                "today": now.date().isoformat(),
            }

        file_name = format_file_name(
            stem=file_stem, suffix=file_suffix, **substitutions
        )

        query = construct_query(query_type=query_type, query_value=query_value)

        # required_resource_keys yields generator
        bq_client: Client = next(context.resources.db_bigquery)

        query_job = bq_client.query(query=query)

        data = [dict(row) for row in query_job.result()]

        if len(data) == 0:
            context.log.warning("Query returned an empty result")

        transformed_data = transform_data(
            data=data,
            file_suffix=file_suffix,
            file_encoding=file_encoding,
            file_format=file_format,
        )

        del data
        gc.collect()

        load_sftp(
            context=context,
            ssh=getattr(context.resources, f"ssh_{destination_name}"),
            data=transformed_data,
            file_name=file_name,
            destination_path=destination_path,
        )

    return _asset
