import gc
import gzip
import json
import pathlib
import re

import pendulum
from dagster import AssetExecutionContext, AssetKey, asset
from dagster_gcp import BigQueryResource, GCSResource
from google.cloud import bigquery, storage
from pandas import DataFrame
from sqlalchemy import literal_column, select, table, text

from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.utils.classes import CustomJSONEncoder


def construct_query(query_type, query_value, now):
    if query_type == "text":
        return text(query_value)
    elif query_type == "file":
        sql_file = pathlib.Path(query_value).absolute()
        with sql_file.open(mode="r") as f:
            return text(f.read())
    elif query_type == "schema":
        return (
            select(*[literal_column(col) for col in query_value.get("select", ["*"])])
            .select_from(table(**query_value["table"]))
            .where(
                text(query_value.get("where", "").format(today=now.to_date_string()))
            )
        )


def transform_data(data, file_suffix, file_encoding=None, file_format=None):
    if file_suffix == "json":
        transformed_data = json.dumps(obj=data, cls=CustomJSONEncoder).encode(
            file_encoding
        )
        del data
        gc.collect()
    elif file_suffix == "json.gz":
        transformed_data = gzip.compress(
            json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
        )
        del data
        gc.collect()
    elif file_suffix in ["csv", "txt", "tsv"]:
        transformed_data = (
            DataFrame(data=data)
            .to_csv(index=False, encoding=file_encoding, **file_format)
            .encode(file_encoding)
        )
        del data
        gc.collect()
    elif file_suffix == "gsheet":
        df = DataFrame(data=data)
        del data
        gc.collect()

        df_json = df.to_json(orient="split", date_format="iso", index=False)
        del df
        gc.collect()

        transformed_data = json.loads(df_json)
        del df_json
        gc.collect()

        transformed_data["shape"] = df.shape

    return transformed_data


def load_sftp(
    context: AssetExecutionContext,
    ssh: SSHConfigurableResource,
    data,
    file_name,
    destination_path,
):
    conn = ssh.get_connection()

    with conn.open_sftp() as sftp:
        sftp.chdir(".")
        cwd_path = pathlib.Path(sftp.getcwd())

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

        context.log.info(f"Saving file to {destination_filepath}")
        if isinstance(data, storage.Blob):
            with sftp.open(filename=str(destination_filepath), mode="w") as f:
                data.download_to_file(file_obj=f)
        else:
            # if destination_path given, chdir after confirming
            if destination_path:
                sftp.chdir(str(destination_filepath.parent))

            with sftp.file(filename=file_name, mode="w") as f:
                f.write(data)


def build_bigquery_query_sftp_asset(
    code_location,
    timezone,
    query_config,
    file_config,
    destination_config,
    op_tags={},
):
    now = pendulum.now(tz=timezone)

    destination_name = destination_config["name"]
    destination_path = destination_config.get("path", "")

    file_suffix = file_config["suffix"]
    file_stem = file_config["stem"]

    file_stem_fmt = file_stem.format(
        today=now.to_date_string(), now=str(now.timestamp()).replace(".", "_")
    )

    file_name = f"{file_stem_fmt}.{file_suffix}"
    asset_name = (
        re.sub(pattern="[^A-Za-z0-9_]", repl="", string=file_stem) + f"_{file_suffix}"
    )

    @asset(
        key=[code_location, "extracts", destination_name, asset_name],
        deps=[
            AssetKey(
                [code_location, "extracts", query_config["value"]["table"]["name"]]
            )
        ],
        metadata={**query_config, **file_config},
        required_resource_keys={"gcs", "db_bigquery", f"ssh_{destination_name}"},
        op_tags=op_tags,
    )
    def _asset(context: AssetExecutionContext):
        query = construct_query(
            query_type=query_config["type"], query_value=query_config["value"], now=now
        )

        db_bigquery: bigquery.Client = next(context.resources.db_bigquery)

        query_job = db_bigquery.query(query=str(query))

        data = [dict(row) for row in query_job.result()]

        if len(data) == 0:
            context.log.warn("Query returned an empty result")

        transformed_data = transform_data(
            data=data,
            file_suffix=file_suffix,
            file_encoding=file_config.get("encoding", "utf-8"),
            file_format=file_config.get("format", {}),
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
    extract_job_config={},
    op_tags={},
):
    now = pendulum.now(tz=timezone)

    dataset_id = dataset_config["dataset_id"]
    table_id = dataset_config["table_id"]

    destination_name = destination_config["name"]
    destination_path = destination_config.get("path", "")

    file_suffix = file_config["suffix"]
    file_stem = file_config["stem"]

    file_stem_fmt = file_stem.format(
        today=now.to_date_string(), now=str(now.timestamp()).replace(".", "_")
    )

    file_name = f"{file_stem_fmt}.{file_suffix}"
    asset_name = (
        re.sub(pattern="[^A-Za-z0-9_]", repl="", string=file_stem) + f"_{file_suffix}"
    )

    @asset(
        key=[code_location, "extracts", destination_name, asset_name],
        deps=[AssetKey([code_location, "extracts", table_id])],
        required_resource_keys={"gcs", "db_bigquery", f"ssh_{destination_name}"},
        op_tags=op_tags,
    )
    def _asset(context: AssetExecutionContext):
        # establish gcs blob
        gcs: storage.Client = context.resources.gcs

        bucket = gcs.get_bucket(f"teamster-{code_location}")

        blob = bucket.blob(
            blob_name=(
                f"dagster/{code_location}/extracts/data/{destination_name}/{file_name}"
            )
        )

        # execute bq extract job
        bq_client = next(context.resources.db_bigquery)

        dataset_ref = bigquery.DatasetReference(
            project=bq_client.project, dataset_id=dataset_id
        )

        extract_job = bq_client.extract_table(
            source=dataset_ref.table(table_id=table_id),
            destination_uris=[f"gs://teamster-{code_location}/{blob.name}"],
            job_config=bigquery.ExtractJobConfig(**extract_job_config),
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
    extract_job_config={},
    op_tags={},
):
    now = pendulum.now(tz=timezone)

    dataset_id = dataset_config["dataset_id"]
    table_id = dataset_config["table_id"]

    destination_name = destination_config["name"]
    destination_path = destination_config.get("path", "")

    file_suffix = file_config["suffix"]
    file_stem = file_config["stem"]

    file_stem_fmt = file_stem.format(
        today=now.to_date_string(), now=str(now.timestamp()).replace(".", "_")
    )

    file_name = f"{file_stem_fmt}.{file_suffix}"
    asset_name = (
        re.sub(pattern="[^A-Za-z0-9_]", repl="", string=file_stem) + f"_{file_suffix}"
    )

    @asset(
        key=[code_location, "extracts", destination_name, asset_name],
        deps=[AssetKey([code_location, "extracts", table_id])],
        op_tags=op_tags,
    )
    def _asset(
        context: AssetExecutionContext, gcs: GCSResource, db_bigquery: BigQueryResource
    ):
        # establish gcs blob
        gcs_client = gcs.get_client()

        bucket = gcs_client.get_bucket(f"teamster-{code_location}")

        blob = bucket.blob(
            blob_name=f"{destination_path}/{destination_name}/{file_name}"
        )

        # execute bq extract job
        with db_bigquery.get_client() as bq_client:
            dataset_ref = bigquery.DatasetReference(
                project=bq_client.project, dataset_id=dataset_id
            )

            extract_job = bq_client.extract_table(
                source=dataset_ref.table(table_id=table_id),
                destination_uris=[f"gs://teamster-{code_location}/{blob.name}"],
                job_config=bigquery.ExtractJobConfig(**extract_job_config),
            )

            extract_job.result()

    return _asset
