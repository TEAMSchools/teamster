from teamster.core.dbt.assets import build_external_source_asset, build_staging_assets
from teamster.kippnewark import CODE_LOCATION
from teamster.kippnewark.powerschool.db.assets import (
    all_assets,
    hourly_partitions_def,
    nonpartition_assets,
    partition_assets,
)

manifest_json_path = f"teamster-dbt/{CODE_LOCATION}/target/manifest.json"
key_prefix = [CODE_LOCATION, "dbt", "powerschool"]

src_assets = [build_external_source_asset(a) for a in all_assets]

nonpartition_stg_assets = build_staging_assets(
    manifest_json_path=manifest_json_path,
    key_prefix=key_prefix,
    assets=nonpartition_assets,
)

incremental_stg_assets = build_staging_assets(
    manifest_json_path=manifest_json_path,
    key_prefix=key_prefix,
    assets=partition_assets,
    partitions_def=hourly_partitions_def,
)

__all__ = src_assets + incremental_stg_assets + nonpartition_stg_assets
