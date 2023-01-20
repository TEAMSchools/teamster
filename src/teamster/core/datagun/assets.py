import gzip
import json
import pathlib

import pandas as pd
from dagster import asset, config_from_files
from sqlalchemy import literal_column, select, table, text

from teamster.core.utils.classes import CustomJSONEncoder
from teamster.core.utils.variables import NOW, TODAY


def construct_sql(query_type, query_value):
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
            .where(text(query_value.get("where", "").format(today=TODAY.isoformat())))
        )


def transform(data, file_suffix, file_encoding=None, file_format=None):
    if file_suffix == "json":
        return json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
    elif file_suffix == "json.gz":
        return gzip.compress(
            json.dumps(obj=data, cls=CustomJSONEncoder).encode(file_encoding)
        )

    df = pd.DataFrame(data=data)
    if file_suffix in ["csv", "txt", "tsv"]:
        return df.to_csv(index=False, encoding=file_encoding, **file_format).encode(
            file_encoding
        )
    elif file_suffix == "gsheet":
        df_json = df.to_json(orient="split", date_format="iso", index=False)

        df_dict = json.loads(df_json)
        df_dict["shape"] = df.shape

        return df_dict


def load_sftp(context, data, file_name, destination_config):
    destination_name = destination_config.get("name")
    destination_path = destination_config.get("path", "")

    # context.resources is a namedtuple
    sftp = getattr(context.resources, f"sftp_{destination_name}")

    sftp_conn = sftp.get_connection()
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

        context.log.info(f"Saving file to {destination_filepath}")
        with sftp.file(file_name, "w") as f:
            f.write(data)


def load_gsheet(context, data, file_stem):
    if file_stem[0].isnumeric():
        file_stem = "GS" + file_stem

    context.resources.gsheets.update_named_range(
        data=data, spreadsheet_name=file_stem, range_name=file_stem
    )


def sftp_extract_asset_factory(
    asset_name, key_prefix, query_config, file_config, destination_config, op_tags={}
):
    @asset(
        name=asset_name,
        key_prefix=key_prefix,
        required_resource_keys={"warehouse", f"sftp_{destination_config['name']}"},
        op_tags=op_tags,
    )
    def sftp_extract(context):
        file_suffix = file_config["suffix"]
        file_stem = file_config["stem"].format(
            today=TODAY.date().isoformat(), now=str(NOW.timestamp()).replace(".", "_")
        )

        sql = construct_sql(
            query_type=query_config["type"], query_value=query_config["value"]
        )

        data = context.resources.warehouse.execute_query(
            query=sql,
            partition_size=query_config.get("partition_size", 100000),
            output="dict",
        )

        if data:
            context.log.info(f"Transforming data to {file_suffix}")
            transformed_data = transform(
                data=data,
                file_suffix=file_suffix,
                file_encoding=file_config.get("encoding", "utf-8"),
                file_format=file_config.get("format", {}),
            )

            load_sftp(
                context=context,
                data=transformed_data,
                file_name=f"{file_stem}.{file_suffix}",
                destination_config=destination_config,
            )

    return sftp_extract


def gsheet_extract_asset_factory(asset_name, query_config, file_config, op_tags={}):
    @asset(
        name=asset_name,
        key_prefix="gsheets",
        required_resource_keys={"warehouse", "gsheets"},
        op_tags=op_tags,
    )
    def gsheet_extract(context):
        file_stem = file_config["stem"].format(
            today=TODAY.date().isoformat(), now=str(NOW.timestamp()).replace(".", "_")
        )

        sql = construct_sql(
            query_type=query_config["type"], query_value=query_config["value"]
        )

        data = context.resources.warehouse.execute_query(
            query=sql,
            partition_size=query_config.get("partition_size", 100000),
            output="dict",
        )

        if data:
            context.log.info("Transforming data to gsheet")
            transformed_data = transform(data=data, file_suffix="gsheet")

            load_gsheet(context=context, data=transformed_data, file_stem=file_stem)

    return gsheet_extract


def generate_extract_assets(code_location, name, extract_type):
    assets = []
    for cfg in config_from_files(
        [f"src/teamster/{code_location}/datagun/config/assets/{name}.yaml"]
    )["assets"]:
        if extract_type == "sftp":
            assets.append(sftp_extract_asset_factory(**cfg))
        elif extract_type == "gsheet":
            assets.append(gsheet_extract_asset_factory(**cfg))
    return assets
