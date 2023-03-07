from teamster.core.dbt.assets import build_external_source_asset, build_staging_assets
from teamster.test import CODE_LOCATION, deanslist, powerschool

manifest_json_path = f"teamster-dbt/{CODE_LOCATION}/target/manifest.json"
key_prefix = [CODE_LOCATION, "dbt"]

# powerschool
powerschool_src_assets = [
    build_external_source_asset(a) for a in powerschool.db.assets.__all__
]
powerschool_nonpartition_stg_assets = build_staging_assets(
    manifest_json_path=manifest_json_path,
    key_prefix=key_prefix,
    assets=powerschool.db.assets.nonpartition_assets,
)
powerschool_incremental_stg_assets = build_staging_assets(
    manifest_json_path=manifest_json_path,
    key_prefix=key_prefix,
    assets=powerschool.db.assets.partition_assets,
    partitions_def=powerschool.db.assets.dynamic_partitions_def,
)

# deanslist
deanslist_src_assets = [
    build_external_source_asset(a) for a in deanslist.assets.__all__
]

__all__ = [
    *powerschool_src_assets,
    *powerschool_incremental_stg_assets,
    *powerschool_nonpartition_stg_assets,
    *deanslist_src_assets,
]
