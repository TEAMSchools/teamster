import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import QUERY_CONFIG
from teamster.core.ops.powerschool.db import extract
from teamster.core.utils.variables import TODAY


@config_mapping(config_schema=QUERY_CONFIG)
def construct_query_config(config):
    query_config = config["query"]
    destination_config = config["destination"]

    [(query_type, output_fmt, value)] = query_config["sql"].items()
    if query_type == "text":
        table_name = "query"
        query = text(value)
    elif query_type == "file":
        query_file = pathlib.Path(value).absolute()
        table_name = query_file.stem
        with query_file.open(mode="r") as f:
            query = text(f.read())
    elif query_type == "schema":
        table_name = value["table"]["name"]
        where_fmt = value.get("where", "").format(today=TODAY.date().isoformat())
        query = (
            select(*[literal_column(col) for col in value["select"]])
            .select_from(table(**value["table"]))
            .where(text(where_fmt))
        )

    return {
        "extract": {
            "config": {
                "query": query,
                "table_name": table_name,
                "output_fmt": output_fmt,
                "destination_type": destination_config["type"],
            }
        }
    }


@graph(config=construct_query_config)
def query():
    extract()


@graph
def generate_queries():
    pass
