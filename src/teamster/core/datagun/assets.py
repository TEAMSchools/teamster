import gc
import gzip
import json
import pathlib
import re

import pendulum
from dagster import AssetExecutionContext, AssetKey, asset, config_from_files
from google.cloud import bigquery, storage
from pandas import DataFrame
from sqlalchemy import literal_column, select, table, text

from teamster.core.google.resources.sheets import GoogleSheetsResource
from teamster.core.sqlalchemy.resources import MSSQLResource
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


def build_sql_query_sftp_asset(
    asset_name,
    key_prefix,
    query_config,
    file_config,
    destination_config,
    timezone,
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
    # asset_name = (
    #     re.sub(pattern="[^A-Za-z0-9_]", repl="", string=file_stem) + f"_{file_suffix}"
    # )

    @asset(
        name=asset_name,
        key_prefix=key_prefix,
        metadata={**query_config, **file_config},
        required_resource_keys={"db_mssql", f"ssh_{destination_config['name']}"},
        op_tags=op_tags,
    )
    def sftp_extract(context):
        sql = construct_query(
            query_type=query_config["type"], query_value=query_config["value"], now=now
        )

        data = context.resources.db_mssql.engine.execute_query(
            query=sql,
            partition_size=query_config.get("partition_size", 100000),
            output_format="dict",
        )

        if data:
            context.log.info(f"Transforming data to {file_suffix}")
            transformed_data = transform_data(
                data=data,
                file_suffix=file_suffix,
                file_encoding=file_config.get("encoding", "utf-8"),
                file_format=file_config.get("format", {}),
            )

            load_sftp(
                context=context,
                ssh=getattr(context.resources, f"ssh_{destination_name}"),
                data=transformed_data,
                file_name=file_name,
                destination_path=destination_path,
            )

    return sftp_extract


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
        key_prefix=[code_location, "extracts", destination_name, asset_name],
        non_argument_deps=[
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

        if data:
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
        non_argument_deps=[AssetKey([code_location, dataset_id, table_id])],
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
            project=bq_client.project, dataset_id=f"{code_location}_{dataset_id}"
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


def gsheet_extract_asset_factory(
    asset_name, key_prefix, query_config, file_config, timezone, folder_id, op_tags={}
):
    now = pendulum.now(tz=timezone)

    @asset(name=asset_name, key_prefix=key_prefix, op_tags=op_tags)
    def gsheet_extract(
        context: AssetExecutionContext,
        db_mssql: MSSQLResource,
        gsheets: GoogleSheetsResource,
    ):
        file_stem: str = file_config["stem"].format(
            today=now.to_date_string(), now=str(now.timestamp()).replace(".", "_")
        )

        # gsheet title first character must be alpha
        if file_stem[0].isnumeric():
            file_stem = "GS" + file_stem

        data = db_mssql.engine.execute_query(
            query=construct_query(
                query_type=query_config["type"],
                query_value=query_config["value"],
                now=now,
            ),
            partition_size=query_config.get("partition_size", 100000),
            output_format="dict",
        )

        if not data:
            return None

        context.log.info("Transforming data to gsheet")
        transformed_data = transform_data(data=data, file_suffix="gsheet")

        context.log.info(f"Opening: {file_stem}")
        spreadsheet = gsheets.open_or_create_sheet(title=file_stem, folder_id=folder_id)

        context.log.debug(spreadsheet.url)

        named_range_match = [
            nr for nr in spreadsheet.list_named_ranges() if nr["name"] == file_stem
        ]

        if named_range_match:
            named_range = named_range_match[0]["range"]
            named_range_id = named_range_match[0]["namedRangeId"]

            named_range_sheet_id = named_range.get("sheetId", 0)
            end_row_ix = named_range.get("endRowIndex", 0)
            end_col_ix = named_range.get("endColumnIndex", 0)

            range_area = (end_row_ix + 1) * (end_col_ix + 1)
        else:
            named_range_id = None
            range_area = 0

        worksheet = (
            spreadsheet.get_worksheet_by_id(id=named_range_sheet_id)
            if named_range_id
            else spreadsheet.sheet1
        )

        nrows, ncols = transformed_data["shape"]
        nrows = nrows + 1  # header row
        transformed_data_area = nrows * ncols

        # resize worksheet
        worksheet_area = worksheet.row_count * worksheet.col_count
        if worksheet_area != transformed_data_area:
            context.log.debug(f"Resizing worksheet area to {nrows}x{ncols}.")
            worksheet.resize(rows=nrows, cols=ncols)

        # resize named range
        if range_area != transformed_data_area:
            start_cell = gsheets.rowcol_to_a1(1, 1)
            end_cell = gsheets.rowcol_to_a1(nrows, ncols)

            context.log.debug(
                f"Resizing named range '{file_stem}' to {start_cell}:{end_cell}."
            )

            worksheet.delete_named_range(named_range_id=named_range_id)
            worksheet.define_named_range(
                name=f"{start_cell}:{end_cell}", range_name=file_stem
            )

        context.log.debug(f"Clearing '{file_stem}' values.")
        worksheet.batch_clear([file_stem])

        context.log.info(f"Updating '{file_stem}': {transformed_data_area} cells.")
        worksheet.update(
            file_stem, [transformed_data["columns"]] + transformed_data["data"]
        )

    return gsheet_extract


def generate_extract_assets(code_location, name, extract_type, timezone):
    cfg = config_from_files(
        [f"src/teamster/{code_location}/datagun/config/{name}.yaml"]
    )

    assets = []
    for ac in cfg["assets"]:
        if extract_type == "sftp":
            assets.append(
                build_sql_query_sftp_asset(
                    key_prefix=cfg["key_prefix"], timezone=timezone, **ac
                )
            )
        elif extract_type == "gsheet":
            assets.append(
                gsheet_extract_asset_factory(
                    key_prefix=cfg["key_prefix"],
                    folder_id=cfg["folder_id"],
                    timezone=timezone,
                    **ac,
                )
            )

    return assets
