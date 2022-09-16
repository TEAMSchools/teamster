import pathlib

from dagster import Field, GraphDefinition, Permissive, config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import QUERY_CONFIG
from teamster.core.ops.powerschool.db import extract
from teamster.core.utils.variables import TODAY


@config_mapping(
    config_schema={
        **QUERY_CONFIG,
        "ssh_tunnel": Field(Permissive(), is_required=False, default_value={}),
    }
)
def construct_query_config(config):
    ssh_tunnel_config = config["ssh_tunnel"]
    query_config = config["query"]
    destination_config = config["destination"]

    [(query_type, output_fmt, value)] = query_config["sql"].items()
    if query_type == "text":
        query = text(value)
    elif query_type == "file":
        query_file = pathlib.Path(value).absolute()
        with query_file.open(mode="r") as f:
            query = text(f.read())
    elif query_type == "schema":
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
                "output_fmt": output_fmt,
                "destination_type": destination_config["type"],
                "ssh_tunnel": ssh_tunnel_config,
            }
        }
    }


@graph
def generate_queries():
    for tbl in ["bell_schedule", "calendar_day", "cycle_day"]:
        return GraphDefinition(
            name=tbl, node_defs=[extract], config=construct_query_config
        )
