from teamster.core.dbt.assets import build_external_source_asset, build_staging_assets
from teamster.test import CODE_LOCATION, deanslist, powerschool

key_prefix = [CODE_LOCATION, "dbt"]

dbt_src_assets = [
    build_external_source_asset(a)
    for a in [*powerschool.db.assets.__all__, *deanslist.assets.__all__]
]

powerschool_stg_assets = build_staging_assets(
    manifest_json_path=f"teamster-dbt/{CODE_LOCATION}/target/manifest.json",
    key_prefix=key_prefix,
    assets=powerschool.db.assets.__all__,
)

__all__ = [
    *dbt_src_assets,
    *powerschool_stg_assets,
]
