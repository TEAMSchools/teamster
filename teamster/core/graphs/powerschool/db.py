import pathlib

from dagster import config_mapping, graph
from dagster._utils import merge_dicts
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import PS_DB_CONFIG
from teamster.core.ops.powerschool.db import extract
from teamster.core.utils.variables import TODAY


@config_mapping(config_schema=merge_dicts(PS_DB_CONFIG))
def construct_graph_config(config):
    query_config = config["query"]
    destination_config = config["destination"]

    [(sql_key, sql_value)] = query_config["sql"].items()
    if sql_key == "text":
        query = text(sql_value)
    elif sql_key == "file":
        query_file = pathlib.Path(sql_value).absolute()
        with query_file.open(mode="r") as f:
            query = text(f.read())
    elif sql_key == "schema":
        where_fmt = sql_value.get("where", "").format(today=TODAY.date().isoformat())
        query = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(where_fmt))
        )

    return {
        "extract": {
            "config": {
                "query": query,
                "output_fmt": query_config["output_fmt"],
                "destination_type": destination_config["type"],
            }
        }
    }


@graph(config=construct_graph_config)
def foo():
    extract()


@graph
def bar():
    bell_schedule = foo.alias("bell_schedule")
    bell_schedule()

    calendar_day = foo.alias("calendar_day")
    calendar_day()
