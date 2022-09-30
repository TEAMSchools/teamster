import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.datagun.config.schema import DATAGUN_CONFIG
from teamster.core.datagun.ops import extract, load_gsheet, load_sftp, transform


@config_mapping(config_schema=DATAGUN_CONFIG)
def construct_graph_config(config):
    query_config = config["query"]
    [(sql_key, sql_value)] = query_config["sql"].items()
    if sql_key == "text":
        sql = text(sql_value)
        table_name = "data"
    elif sql_key == "file":
        sql_file = pathlib.Path(sql_value).absolute()
        table_name = sql_file.stem
        with sql_file.open(mode="r") as f:
            sql = text(f.read())
    elif sql_key == "schema":
        sql = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(sql_value.get("where", "")))
        )
        table_name = sql_value["table"]["name"]

    destination_name = config["destination"].get("name", (table_name or "data"))
    destination_type = config["destination"]["type"]

    graph_config = {
        "extract": {
            "config": {
                "sql": sql,
                "partition_size": query_config["partition_size"],
                "output_fmt": query_config["output_fmt"],
            }
        },
        "transform": {
            "config": {
                "file": config["file"],
                "destination_name": destination_name,
                "destination_type": destination_type,
            }
        },
    }

    if destination_type == "sftp":
        graph_config["load_sftp"] = {
            "config": {"destination_path": config["destination"]["path"]}
        }
    elif destination_type == "gsheet":
        graph_config["load_gsheet"] = {"config": {"file_stem": config["file"]["stem"]}}

    return graph_config


@graph(config=construct_graph_config)
def etl_sftp():
    data = extract()

    file_handle, df_dict = transform(data=data)

    load_sftp(file_handle=file_handle)


@graph(config=construct_graph_config)
def etl_gsheet():
    data = extract()

    file_handle, df_dict = transform(data=data)

    load_gsheet(df_dict=df_dict)


@graph
def test_etl():
    test_gsheet = etl_gsheet.alias("test_gsheet")
    test_gsheet()

    test_sftp_1 = etl_sftp.alias("test_sftp_1")
    test_sftp_1()

    test_sftp_2 = etl_sftp.alias("test_sftp_2")
    test_sftp_2()
