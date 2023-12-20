import pathlib

import yaml
from dagster import AssetKey, AssetsDefinition, AssetSpec

from teamster.core.definitions.external_asset import external_assets_from_specs
from teamster.kipptaf import CODE_LOCATION

config_path = pathlib.Path(__file__).parent / "config"

specs = []
for config_file in config_path.glob("*.yaml"):
    config = yaml.safe_load(config_file.read_text())

    connector_name = config["connector_name"]

    asset_key_prefix = [CODE_LOCATION, connector_name]

    for schema in config["schemas"]:
        schema_name = schema.get("name")

        if schema_name is not None:
            asset_key_prefix.append(schema_name)

        for table in schema["destination_tables"]:
            specs.append(
                AssetSpec(
                    key=AssetKey([*asset_key_prefix, table]),
                    group_name=config.get("group_name", connector_name),
                    metadata={"connector_id": config["connector_id"]},
                )
            )

_all: list[AssetsDefinition] = external_assets_from_specs(
    specs=specs, compute_kind="fivetran"
)
