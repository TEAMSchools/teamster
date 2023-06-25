import json

from dagster_dbt import load_assets_from_dbt_manifest

from teamster.core.dbt.assets import build_external_source_asset_from_key
from teamster.kipptaf import CODE_LOCATION, fivetran, google

with open(file=f"teamster-dbt/{CODE_LOCATION}/target/manifest.json") as f:
    manifest_json = json.load(f)

dbt_assets = load_assets_from_dbt_manifest(
    manifest_json=manifest_json,
    key_prefix=[CODE_LOCATION, "dbt"],
    source_key_prefix=[CODE_LOCATION, "dbt"],
)

fivetran_source_assets = [
    build_external_source_asset_from_key(asset_key=asset_key)
    for assets in fivetran.assets
    for assets_def in assets.compute_cacheable_data()
    for table_name, asset_key in assets_def.keys_by_output_name.items()
]

gsheet_source_assets = [
    build_external_source_asset_from_key(
        asset_key=asset.key, group_name=asset.key.path[-1].split("__")[0]
    )
    for asset in google.assets
]

__all__ = [
    *dbt_assets,
    *fivetran_source_assets,
    *gsheet_source_assets,
]
