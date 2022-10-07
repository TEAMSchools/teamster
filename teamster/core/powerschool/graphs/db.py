import pathlib

import yaml
from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.powerschool.config.db import schema
from teamster.core.powerschool.ops.db import extract_to_data_lake, get_counts_factory


def get_table_names(instance, table_set):
    file_path = f"teamster/{instance}/powerschool/config/db/sync-{table_set}.yaml"

    with open(file=file_path) as f:
        config_yaml = yaml.safe_load(f.read())

    table_configs = config_yaml["ops"]["config"]["queries"]
    return [t["sql"]["schema"]["table"]["name"] for t in table_configs]


@config_mapping(config_schema=schema.TABLES_CONFIG)
def construct_sync_table_multi_config(config):
    constructed_config = {"get_counts": {"config": {"queries": []}}}

    for query in config["queries"]:
        sql_config = query["sql"]

        table_name = sql_config["schema"]["table"]["name"]
        constructed_config[table_name] = {"config": {"sql": sql_config}}

        sql = None
        [(sql_key, sql_value)] = sql_config.items()
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

        constructed_config["get_counts"]["config"]["queries"].append(sql)

    return constructed_config


@config_mapping(config_schema=schema.QUERY_CONFIG)
def construct_sync_table_config(config):
    return {
        "extract_to_data_lake": {"config": {"partition_size": config["partition_size"]}}
    }


@graph(config=construct_sync_table_config)
def sync_table(sql):
    extract_to_data_lake(sql)


def sync_table_multi_factory(instance, table_set):
    table_names = get_table_names(instance=instance, table_set=table_set)

    @graph(config=construct_sync_table_multi_config)
    def sync_table_multi():
        get_counts = get_counts_factory(table_names=table_names)
        valid_tables = get_counts()

        for tbl in table_names:
            sync_table_inst = sync_table.alias(tbl)
            sync_table_inst(getattr(valid_tables, tbl))

    return sync_table_multi


sync_standard = sync_table_multi_factory(instance="core", table_set="standard")


# @graph
# def test_sync_table():
#     sync_table_inst = sync_table.alias("test_sync_table")
#     sync_table_inst()
