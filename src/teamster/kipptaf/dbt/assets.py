import json

from dagster_dbt.cli import DbtManifest

from teamster.core.dbt.assets import build_dbt_assets, build_staging_assets_from_source
from teamster.kipptaf import CODE_LOCATION, fivetran, google

manifest_path = f"teamster-dbt/{CODE_LOCATION}/target/manifest.json"

manifest = DbtManifest.read(path=manifest_path)

with open(file=manifest_path) as f:
    manifest_json = json.load(f)

dbt_assets = build_dbt_assets(manifest=manifest)

fivetran_source_assets = [
    build_staging_assets_from_source(
        manifest=manifest,
        code_location=CODE_LOCATION,
        table_name=object_identifier.split(sep=".")[1],
        dbt_package_name=object_identifier.split(sep=".")[0],
        upstream_package_name=asset_key.path[1],
        group_name=asset_key.path[1],
    )
    for assets in fivetran.assets
    for assets_def in assets.compute_cacheable_data()
    for object_identifier, asset_key in assets_def.keys_by_output_name.items()
]

gsheet_source_assets = [
    build_staging_assets_from_source(
        manifest=manifest,
        code_location=CODE_LOCATION,
        table_name=asset.key.path[-1].split("__")[1],
        dbt_package_name=asset.key.path[-1].split("__")[0],
        upstream_package_name=asset.key.path[1],
        group_name=asset.key.path[-1].split("__")[0],
    )
    for asset in google.assets
]

__all__ = [
    dbt_assets,
    *fivetran_source_assets,
    *gsheet_source_assets,
]
