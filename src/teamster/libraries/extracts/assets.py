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
    _check,
    asset,
)
from dagster_gcp import BigQueryResource, GCSResource
from google.cloud.bigquery import Client as BigQueryClient
from google.cloud.bigquery import DatasetReference, ExtractJobConfig
from google.cloud.storage import Blob
from google.cloud.storage import Client as CloudStorageClient
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
        _check.not_none(value=sftp.get_channel()).settimeout(ssh.timeout)

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
            with sftp.open(filename=str(destination_filepath), mode="w") as f:
                data.download_to_file(file_obj=f)
        else:
            # if destination_path given, chdir after confirming
            if destination_path:
                context.log.info(f"Changing directory to {destination_filepath.parent}")
                sftp.chdir(str(destination_filepath.parent))

            context.log.info(f"Saving file to {destination_filepath}")
            with sftp.file(filename=file_name, mode="w") as f:
                f.write(data)


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
        deps=[AssetKey([code_location, "extracts", query_value["table"]["name"]])],
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
            partition_key = _check.inst(
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

        db_bigquery: BigQueryClient = next(context.resources.db_bigquery)

        query_job = db_bigquery.query(query=query)

        data = [dict(row) for row in query_job.result()]

        if len(data) == 0:
            context.log.warn("Query returned an empty result")

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


def build_bigquery_extract_sftp_asset(
    code_location,
    timezone,
    dataset_config,
    file_config,
    destination_config,
    extract_job_config: dict | None = None,
    op_tags: dict | None = None,
    partitions_def=None,
):
    if extract_job_config is None:
        extract_job_config = {}

    dataset_id = dataset_config["dataset_id"]
    table_id = dataset_config["table_id"]

    destination_name = destination_config["name"]
    destination_path = destination_config.get("path", "")

    file_suffix = file_config["suffix"]
    file_stem = file_config["stem"]

    asset_name = (
        re.sub(pattern="[^A-Za-z0-9_]", repl="", string=file_stem) + f"_{file_suffix}"
    )

    @asset(
        key=[code_location, "extracts", destination_name, asset_name],
        deps=[AssetKey([code_location, "extracts", table_id])],
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
            partition_key = _check.inst(
                obj=context.partition_key, ttype=MultiPartitionKey
            )

            substitutions = partition_key.keys_by_dimension
        else:
            substitutions = {
                "now": str(now.timestamp()).replace(".", "_"),
                "today": now.date().isoformat(),
            }

        file_name = format_file_name(
            stem=file_stem, suffix=file_suffix, **substitutions
        )

        # establish gcs blob
        gcs: CloudStorageClient = context.resources.gcs

        bucket = gcs.get_bucket(f"teamster-{code_location}")

        blob = bucket.blob(
            blob_name=(
                f"dagster/{code_location}/extracts/data/{destination_name}/{file_name}"
            )
        )

        # execute bq extract job
        bq_client: BigQueryClient = next(context.resources.db_bigquery)

        dataset_ref = DatasetReference(project=bq_client.project, dataset_id=dataset_id)

        extract_job = bq_client.extract_table(
            source=dataset_ref.table(table_id=table_id),
            destination_uris=[f"gs://teamster-{code_location}/{blob.name}"],
            job_config=ExtractJobConfig(**extract_job_config),
        )

        extract_job.result()

        # transfer via sftp
        load_sftp(
            context=context,
            ssh=getattr(context.resources, f"ssh_{destination_name}"),
            data=blob,
            file_name=file_name,
            destination_path=destination_path,
        )

    return _asset


def build_bigquery_extract_asset(
    code_location,
    timezone,
    dataset_config,
    file_config,
    destination_config,
    extract_job_config: dict | None = None,
    op_tags: dict | None = None,
):
    if extract_job_config is None:
        extract_job_config = {}

    dataset_id = dataset_config["dataset_id"]
    table_id = dataset_config["table_id"]

    destination_name = destination_config["name"]
    destination_path = destination_config.get("path", "")

    file_suffix = file_config["suffix"]
    file_stem = file_config["stem"]

    asset_name = (
        re.sub(pattern="[^A-Za-z0-9_]", repl="", string=file_stem) + f"_{file_suffix}"
    )

    @asset(
        key=[code_location, "extracts", destination_name, asset_name],
        deps=[AssetKey([code_location, "extracts", table_id])],
        op_tags=op_tags,
        group_name="extracts",
        kinds={"python"},
    )
    def _asset(
        context: AssetExecutionContext, gcs: GCSResource, db_bigquery: BigQueryResource
    ):
        now = datetime.now(timezone)

        if context.has_partition_key and isinstance(
            context.assets_def.partitions_def, MultiPartitionsDefinition
        ):
            partition_key = _check.inst(
                obj=context.partition_key, ttype=MultiPartitionKey
            )

            substitutions = partition_key.keys_by_dimension
        else:
            substitutions = {
                "now": str(now.timestamp()).replace(".", "_"),
                "today": now.date().isoformat(),
            }

        file_name = format_file_name(
            stem=file_stem, suffix=file_suffix, **substitutions
        )

        # establish gcs blob
        gcs_client = gcs.get_client()

        bucket = gcs_client.get_bucket(f"teamster-{code_location}")

        blob = bucket.blob(
            blob_name=f"{destination_path}/{destination_name}/{file_name}"
        )

        # execute bq extract job
        with db_bigquery.get_client() as bq_client:
            dataset_ref = DatasetReference(
                project=bq_client.project, dataset_id=dataset_id
            )

            extract_job = bq_client.extract_table(
                source=dataset_ref.table(table_id=table_id),
                destination_uris=[f"gs://teamster-{code_location}/{blob.name}"],
                job_config=ExtractJobConfig(**extract_job_config),
            )

            extract_job.result()

    return _asset
