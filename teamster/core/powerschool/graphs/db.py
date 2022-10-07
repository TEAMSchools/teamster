import pathlib

import yaml
from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.powerschool.config.db import schema
from teamster.core.powerschool.ops.db import extract_to_data_lake, get_counts_factory


def get_table_names(instance, table_set):
    file_path = pathlib.Path(
        f"teamster/{instance}/powerschool/config/db/sync-{table_set}.yaml"
    )

    if file_path.exists():
        with file_path.open("r") as f:
            config_yaml = yaml.safe_load(f.read())

        return [
            t["sql"]["schema"]["table"]["name"]
            for t in config_yaml["ops"]["config"]["queries"]
        ]
    else:
        return []


@config_mapping(config_schema=schema.QUERY_CONFIG)
def construct_sync_table_config(config):
    return {
        "extract_to_data_lake": {"config": {"partition_size": config["partition_size"]}}
    }


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


@graph(config=construct_sync_table_config)
def sync_table(sql):
    extract_to_data_lake(sql)


def sync_table_multi_factory(table_sets):
    table_names = [
        tbl
        for ts in table_sets
        for tbl in get_table_names(instance=ts["instance"], table_set=ts["table_set"])
    ]

    @graph(config=construct_sync_table_multi_config)
    def sync_table_multi():
        get_counts = get_counts_factory(table_names=list(table_names))
        counts_output = get_counts()

        for tbl in table_names:
            sql = getattr(counts_output, tbl)

            sync_table_invocation = sync_table.alias(tbl)
            sync_table_invocation(sql)

    return sync_table_multi


sync_standard = sync_table_multi_factory(
    table_sets=[
        {"instance": "core", "table_set": "standard"},
        {"instance": "local", "table_set": "extensions"},
    ]
)
