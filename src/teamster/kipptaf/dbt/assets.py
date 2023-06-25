import json

from dagster_dbt import load_assets_from_dbt_manifest

from .. import CODE_LOCATION

with open(file=f"teamster-dbt/{CODE_LOCATION}/target/manifest.json") as f:
    manifest_json = json.load(f)

dbt_assets = load_assets_from_dbt_manifest(
    manifest_json=manifest_json,
    key_prefix=[CODE_LOCATION, "dbt"],
    source_key_prefix=[CODE_LOCATION, "dbt"],
)

__all__ = [
    *dbt_assets,
]
