import json

from dagster import AssetKey
from dagster_dbt.cli import DbtManifest

from teamster.core.dbt.assets import build_dbt_assets, build_external_source_asset_new
from teamster.kipptaf import CODE_LOCATION, google


class CustomizedDbtManifest(DbtManifest):
    @classmethod
    def node_info_to_asset_key(cls, node_info):
        dagster_metadata = node_info.get("meta", {}).get("dagster", {})

        asset_key_config = dagster_metadata.get("asset_key", [])

        if asset_key_config:
            return AssetKey(asset_key_config)

        components = [CODE_LOCATION]

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

gsheet_source_assets = [
    build_external_source_asset_new(
        code_location=CODE_LOCATION,
        name="src_" + asset.key.path[-1],
        dbt_package_name=asset.key.path[-1].split("__")[0],
        upstream_asset_key=asset.key,
        group_name=asset.key.path[-1].split("__")[0],
        manifest=manifest,
    )
    for asset in google.assets
]

__all__ = [
    dbt_assets,
    *gsheet_source_assets,
]
