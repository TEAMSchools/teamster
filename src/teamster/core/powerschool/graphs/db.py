import pathlib

import yaml
from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.powerschool.config.db.schema import QUERY_CONFIG, TABLES_CONFIG
from teamster.core.powerschool.ops.db import extract_to_data_lake, get_counts_factory


def get_table_names(instance, table_set, resync):
    file_path = pathlib.Path(
        f"src/teamster/{instance}/powerschool/config/db/sync-{table_set}.yaml"
    )

    if file_path.exists():
        with file_path.open("r") as f:
            config_yaml = yaml.safe_load(f.read())

        queries = config_yaml["ops"]["config"]["queries"]
        table_iterations = {t["sql"]["schema"]["table"]["name"]: 0 for t in queries}

        table_names = []
        for t in queries:
            table_name = t["sql"]["schema"]["table"]["name"]
            if resync:
                table_iterations[table_name] += 1
                table_iteration = f"0{table_iterations[table_name]}"[-2:]

                table_name += f"_R{table_iteration}"

            table_names.append(table_name)

        return table_names
    else:
        return []


@config_mapping(config_schema=QUERY_CONFIG)
def construct_sync_table_config(config):
    return {
        "extract_to_data_lake": {"config": {"partition_size": config["partition_size"]}}
    }


@config_mapping(config_schema=TABLES_CONFIG)
def construct_sync_table_multi_config(config):
    queries = config["queries"]
    resync = config["resync"]
    graph_alias = config["graph_alias"]

    constructed_config = {f"get_counts_{graph_alias}": {"config": {"queries": []}}}

    constructed_config[f"get_counts_{graph_alias}"]["config"]["resync"] = resync

    table_iterations = {t["sql"]["schema"]["table"]["name"]: 0 for t in queries}
    for query in queries:
        sql_config = query["sql"]

        table_name = sql_config["schema"]["table"]["name"]
        if resync:
            table_iterations[table_name] += 1
            table_iteration = f"0{table_iterations[table_name]}"[-2:]
            table_name += f"_R{table_iteration}"

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
            if sql_where is None:
                constructed_sql_where = ""
            elif isinstance(sql_where, str):
                constructed_sql_where = sql_where
            else:
                constructed_sql_where = (
                    f"{sql_where['column']} >= "
                    f"TO_TIMESTAMP_TZ('{{{sql_where['value']}}}', "
                    "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')"
                )

            sql = (
                select(*[literal_column(col) for col in sql_value["select"]])
                .select_from(table(**sql_value["table"]))
                .where(text(constructed_sql_where))
            )

        constructed_config[f"get_counts_{graph_alias}"]["config"]["queries"].append(sql)

    return constructed_config


@graph(config=construct_sync_table_config)
def sync_table(sql):
    extract_to_data_lake(sql)


def sync_table_multi_factory(table_sets, graph_alias, op_alias, resync=False):
    table_names = [
        tbl
        for ts in table_sets
        for tbl in get_table_names(
            instance=ts["instance"], table_set=ts["table_set"], resync=resync
        )
    ]

    @graph(
        name=f"sync_table_multi_{graph_alias}", config=construct_sync_table_multi_config
    )
    def sync_table_multi():
        get_counts = get_counts_factory(table_names=table_names, op_alias=op_alias)
        counts_output = get_counts()

        for table_name in table_names:
            sql = getattr(counts_output, table_name)

            sync_table_invocation = sync_table.alias(table_name)
            sync_table_invocation(sql)

    return sync_table_multi


sync_standard = sync_table_multi_factory(
    table_sets=[
        {"instance": "core", "table_set": "standard"},
        {"instance": "local", "table_set": "extensions"},
    ],
    graph_alias="standard",
    op_alias="standard",
)

resync = sync_table_multi_factory(
    table_sets=[
        {"instance": "local", "table_set": "resync"},
    ],
    graph_alias="resync",
    op_alias="resync",
    resync=True,
)
