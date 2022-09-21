import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import PS_DB_CONFIG
from teamster.core.ops.powerschool.db import extract
from teamster.core.utils.variables import TODAY


@config_mapping(config_schema=PS_DB_CONFIG)
def construct_graph_config(config):
    query_config = config["query"]
    destination_config = config["destination"]

    [(sql_key, sql_value)] = query_config["sql"].items()
    if sql_key == "text":
        query = text(sql_value)
        table_name = "data"
    elif sql_key == "file":
        query_file = pathlib.Path(sql_value).absolute()
        table_name = query_file.stem
        with query_file.open(mode="r") as f:
            query = text(f.read())
    elif sql_key == "schema":
        where_fmt = sql_value.get("where", "").format(today=TODAY.date().isoformat())
        query = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(where_fmt))
        )
        table_name = sql_value["table"]["name"]

    return {
        "extract": {
            "config": {
                "query": query,
                "output_fmt": query_config["output_fmt"],
                "partition_size": query_config["partition_size"],
                "destination_type": destination_config["type"],
                "table_name": table_name,
            }
        }
    }


@graph(config=construct_graph_config)
def sync_table():
    extract()


@graph
def sync_all():
    attendance = sync_table.alias("attendance")
    attendance()

    log = sync_table.alias("log")
    log()

    assignmentscore = sync_table.alias("assignmentscore")
    assignmentscore()

    pgfinalgrades = sync_table.alias("pgfinalgrades")
    pgfinalgrades()

    storedgrades = sync_table.alias("storedgrades")
    storedgrades()
