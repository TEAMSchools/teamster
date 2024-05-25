import pathlib

from dagster import AssetKey, AssetsDefinition, AssetSpec, config_from_files

from teamster.core.definitions.external_asset import external_assets_from_specs

specs = [
    AssetSpec(
        key=AssetKey([a["group_name"], table]),
        metadata={"connection_id": a["connection_id"]},
        group_name=a["group_name"],
    )
    for a in config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])[
        "assets"
    ]
    for table in a["destination_tables"]
]

assets: list[AssetsDefinition] = external_assets_from_specs(
    specs=specs, compute_kind="airbyte"
)
