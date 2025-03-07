import pathlib

import yaml
from dagster import AssetKey, AssetSpec


def build_fivetran_asset_specs(
    config_file: pathlib.Path, code_location: str, kinds: list[str] | None = None
):
    if kinds is None:
        kinds = []

    specs = []

    config = yaml.safe_load(config_file.read_text())

    connector_name, connector_id, group_name, schemas = config.values()

    for schema in schemas:
        asset_key_prefix = [code_location, connector_name]

        schema_name = schema.get("name")

        if schema_name is not None:
            asset_key_prefix.append(schema_name)
            dataset_id = f"{connector_name}_{schema_name}"
        else:
            dataset_id = connector_name

        for table in schema["destination_tables"]:
            specs.append(
                AssetSpec(
                    key=AssetKey([*asset_key_prefix, table]),
                    group_name=group_name,
                    metadata={
                        "connector_id": connector_id,
                        "connector_name": connector_name,
                        "dataset_id": dataset_id,
                        "table_id": table,
                    },
                    kinds={"fivetran", "bigquery", *kinds},
                )
            )

    return specs
