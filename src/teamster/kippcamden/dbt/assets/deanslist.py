from teamster.core.dbt.assets import build_external_source_asset
from teamster.kippcamden import CODE_LOCATION
from teamster.kippcamden.deanslist import assets

manifest_json_path = f"teamster-dbt/{CODE_LOCATION}/target/manifest.json"
key_prefix = [CODE_LOCATION, "dbt"]

src_assets = [build_external_source_asset(a) for a in assets.__all__]

# nonpartition_stg_assets = build_staging_assets(
#     manifest_json_path=manifest_json_path,
#     key_prefix=key_prefix,
#     assets=assets.nonpartition_assets,
# )

# incremental_stg_assets = build_staging_assets(
#     manifest_json_path=manifest_json_path,
#     key_prefix=key_prefix,
#     assets=assets.partition_assets,
#     partitions_def=assets.dynamic_partitions_def,
# )

__all__ = [
    # incremental_stg_assets,
    # nonpartition_stg_assets,
    *src_assets,
]
