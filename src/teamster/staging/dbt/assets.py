from teamster.core.dbt.assets import build_external_source_asset, build_staging_assets

from .. import CODE_LOCATION, deanslist, powerschool

powerschool_dbt_src_assets = [
    build_external_source_asset(a) for a in powerschool.assets
]

powerschool_dbt_stg_assets = build_staging_assets(
    manifest_json_path=f"teamster-dbt/{CODE_LOCATION}/target/manifest.json",
    key_prefix=[CODE_LOCATION, "dbt"],
    assets=powerschool.assets,
)

deanslist_dbt_src_assets = [build_external_source_asset(a) for a in deanslist.assets]

# deanslist_dbt_stg_assets = build_staging_assets(
#     manifest_json_path=f"teamster-dbt/{CODE_LOCATION}/target/manifest.json",
#     key_prefix=[CODE_LOCATION, "dbt"],
#     assets=deanslist.assets.__all__,
# )

__all__ = [
    *powerschool_dbt_src_assets,
    *powerschool_dbt_stg_assets,
    *deanslist_dbt_src_assets,
]
