import json

from dagster import AssetKey, AssetSelection
from dagster_dbt.cli import DbtManifest

from teamster.core.dbt.assets import (
    build_dbt_assets,
    build_external_source_asset_new,
    build_staging_asset_from_source,
)
from teamster.kipptaf import CODE_LOCATION, fivetran


class CustomizedDbtManifest(DbtManifest):
    @classmethod
    def node_info_to_asset_key(cls, node_info):
        dagster_metadata = node_info.get("meta", {}).get("dagster", {})

        asset_key_config = dagster_metadata.get("asset_key", [])

        if asset_key_config:
            return AssetKey(asset_key_config)

        components = [CODE_LOCATION, "dbt"]

        if node_info["resource_type"] == "source":
            components.extend([node_info["source_name"], node_info["name"]])
        else:
            configured_schema = node_info["config"].get("schema")
            if configured_schema is not None:
                components.extend([configured_schema, node_info["name"]])
            else:
                components.extend([node_info["name"]])

        return AssetKey(components)


manifest_path = f"teamster-dbt/{CODE_LOCATION}/target/manifest.json"

with open(file=manifest_path) as f:
    manifest_json = json.load(f)

manifest = CustomizedDbtManifest.read(path=manifest_path)

dbt_assets = build_dbt_assets(manifest=manifest)

fivetran_source_assets = [
    build_external_source_asset_new(
        manifest=manifest,
        code_location=CODE_LOCATION,
        table_name=object_identifier.split(sep=".")[1],
        dbt_package_name=object_identifier.split(sep=".")[0],
        upstream_asset_key=asset_key,
        group_name=asset_key.path[1],
    )
    for assets in fivetran.assets
    for assets_def in assets.compute_cacheable_data()
    for object_identifier, asset_key in assets_def.keys_by_output_name.items()
]

gsheet_source_assets = [
    build_staging_asset_from_source(
        manifest=manifest,
        code_location=CODE_LOCATION,
        table_name=asset_key.path[-1],
        dbt_package_name=asset_key.path[-1].split("__")[0],
        upstream_asset_key=asset_key,
        group_name=asset_key.path[-1].split("__")[0],
    )
    for asset_key in AssetSelection.keys(
        [CODE_LOCATION, "gsheets", "people__employee_numbers_archive"]
    )._keys
]

__all__ = [
    dbt_assets,
    *fivetran_source_assets,
    *gsheet_source_assets,
]
