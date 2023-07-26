import pathlib

import yaml

from teamster.core.fivetran.assets import build_fivetran_assets
from teamster.kipptaf import CODE_LOCATION

config_path = pathlib.Path(__file__).parent / "config"

__all__ = []

for config_file in config_path.glob("*.yaml"):
    config = yaml.safe_load(config_file.read_text())

    connector_name = config["connector_name"]

    destination_tables = []
    for schema in config["schemas"]:
        schema_name = schema.get("name")

        if schema_name:
            destination_table_schema_name = f"{connector_name}.{schema_name}"
        else:
            destination_table_schema_name = connector_name

        for table in schema["destination_tables"]:
            destination_tables.append(f"{destination_table_schema_name}.{table}")

    __all__.extend(
        build_fivetran_assets(
            connector_id=config["connector_id"],
            destination_tables=destination_tables,
            asset_key_prefix=[CODE_LOCATION],
            group_name=config.get("group_name", connector_name),
        )
    )
