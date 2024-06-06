import pathlib

import yaml
from dagster import AssetKey, AssetsDefinition, AssetSpec

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.core.definitions.external_asset import (
    external_assets_from_specs,
)

CONNECTORS = {}

config_path = pathlib.Path(__file__).parent / "config"

specs = []
for config_file in config_path.glob("*.yaml"):
    config = yaml.safe_load(config_file.read_text())

    connector_name = config["connector_name"]
    connector_id = config["connector_id"]

    CONNECTORS[connector_id] = set()

    for schema in config["schemas"]:
        asset_key_prefix = [CODE_LOCATION, connector_name]

        schema_name = schema.get("name")

        if schema_name is not None:
            asset_key_prefix.append(schema_name)

        CONNECTORS[connector_id].add(".".join(asset_key_prefix[1:]))

        for table in schema["destination_tables"]:
            specs.append(
                AssetSpec(
                    key=AssetKey([*asset_key_prefix, table]),
                    group_name=config.get("group_name", connector_name),
                    metadata={"connector_id": connector_id},
                )
            )

assets: list[AssetsDefinition] = external_assets_from_specs(
    specs=specs, compute_kind="fivetran"
)
