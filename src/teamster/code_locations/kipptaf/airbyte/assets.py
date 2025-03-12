import pathlib

from dagster import AssetKey, AssetSpec, config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION


def build_airbyte_asset_specs(config_file):
    config = config_from_files([config_file])

    return [
        AssetSpec(
            key=AssetKey([CODE_LOCATION, config["group_name"], table]),
            metadata={
                "connection_id": config["connection_id"],
                "dataset_id": config["dataset_id"],
                "table_id": table,
            },
            group_name=config["group_name"],
            kinds={"airbyte", "bigquery", *config.get("kinds", [])},
        )
        for table in config["destination_tables"]
    ]


config_dir = pathlib.Path(__file__).parent / "config"

salesforce_asset_specs = build_airbyte_asset_specs(
    f"{config_dir}/salesforce-assets.yaml"
)

asset_specs = [
    *salesforce_asset_specs,
]
