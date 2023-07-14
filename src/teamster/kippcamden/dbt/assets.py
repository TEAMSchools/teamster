import json

from dagster import AssetKey
from dagster_dbt.cli import DbtManifest

from teamster.core.dbt.assets import build_dbt_assets, build_external_source_asset
from teamster.kippcamden import CODE_LOCATION, deanslist, powerschool


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

    # workaround for similarly named sources overriding model name
    @property
    def node_info_by_output_name(self):
        return {
            node["unique_id"].split(".")[-1]: node
            for node in self.node_info_by_dbt_unique_id.values()
            if node["resource_type"] != "source"
        }


manifest_path = f"dbt/{CODE_LOCATION}/target/manifest.json"

with open(file=manifest_path) as f:
    manifest_json = json.load(f)

manifest = CustomizedDbtManifest.read(path=manifest_path)

dbt_assets = build_dbt_assets(manifest=manifest)

external_source_assets = [
    build_external_source_asset(
        code_location=CODE_LOCATION,
        name=f"src_{asset.key.path[1]}__{asset.key.path[-1]}",
        dbt_package_name=asset.key.path[1],
        upstream_asset_key=asset.key,
        group_name=asset.key.path[1],
        manifest=manifest,
    )
    for asset in [*powerschool.assets, *deanslist.assets]
]

__all__ = [
    dbt_assets,
    *external_source_assets,
]
