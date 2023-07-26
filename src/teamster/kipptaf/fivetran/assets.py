import pathlib

import yaml

from teamster.core.fivetran.assets import build_fivetran_asset
from teamster.kipptaf import CODE_LOCATION

config_path = pathlib.Path(__file__).parent / "config"

__all__ = []

for config_file in config_path.glob("*.yaml"):
    config = yaml.safe_load(config_file.read_text())

    for schema in config["schemas"]:
        for table in schema["destination_tables"]:
            __all__.append(
                build_fivetran_asset(
                    name=table,
                    code_location=CODE_LOCATION,
                    schema_name=schema["name"],
                    connector_id=config["connector_id"],
                    group_name=config.get("group_name", config["connector_name"]),
                )
            )
