import yaml


def get_table_names(instance, table_set):
    file_path = f"teamster/{instance}/powerschool/config/db/sync-{table_set}.yaml"

    with open(file=file_path) as f:
        config_yaml = yaml.safe_load(f.read())

    table_configs = config_yaml["ops"]["config"]["queries"]
    return [t["sql"]["schema"]["table"]["name"] for t in table_configs]


STANDARD_TABLES = get_table_names(instance="core", table_set="standard")
