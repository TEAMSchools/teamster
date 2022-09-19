import pathlib

from dagster import Field, Permissive, config_mapping, graph
from dagster._utils import merge_dicts
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import QUERY_CONFIG
from teamster.core.ops.powerschool.db import extract
from teamster.core.utils.variables import TODAY


@config_mapping(
    config_schema=merge_dicts(
        QUERY_CONFIG,
        {"ssh_tunnel": Field(Permissive(), is_required=False, default_value={})},
    )
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


@graph(config=construct_query_config)
def foo():
    extract()


@graph
def bar():
    bell_schedule = foo.alias("bell_schedule")
    bell_schedule()

    calendar_day = foo.alias("calendar_day")
    calendar_day()
