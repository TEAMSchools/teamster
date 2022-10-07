import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.powerschool.config.db import schema, tables
from teamster.core.powerschool.ops.db import extract, get_counts


@config_mapping()
def construct_sync_multi_config(config):
    constructed_config = {}

    for tbl in config.items():
        table_name, config_val = tbl
        constructed_config[table_name] = {"config": config_val}

    return constructed_config


@config_mapping(config_schema=schema.PS_DB_CONFIG)
def construct_sync_table_config(config):
    [(sql_key, sql_value)] = config["sql"].items()
    if sql_key == "text":
        sql = text(sql_value)
    elif sql_key == "file":
        sql_file = pathlib.Path(sql_value).absolute()
        with sql_file.open(mode="r") as f:
            sql = text(f.read())
    elif sql_key == "schema":
        sql_where = sql_value.get("where")
        if sql_where is not None:
            constructed_sql_where = (
                f"{sql_where['column']} >= "
                f"TO_TIMESTAMP_TZ('{{{sql_where['value']}}}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')"
            )

        else:
            constructed_sql_where = ""

        sql = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(constructed_sql_where))
        )

    return {
        "extract": {
            "config": {
                "sql": sql,
                "partition_size": config["partition_size"],
            }
        }
    }


@graph(config=construct_sync_table_config)
def sync_table(has_count):
    extract(has_count)


@graph(config=construct_sync_multi_config)
def sync():  # TODO: rename to sync_standard
    valid_tables = get_counts()

    for tbl in tables.STANDARD_TABLES:
        sync_table_inst = sync_table.alias(tbl)
        sync_table_inst(getattr(valid_tables, tbl))


# @graph
# def test_sync_table():
#     sync_table_inst = sync_table.alias("test_sync_table")
#     sync_table_inst()
