from teamster.core.dbt.assets import build_dbt_assets, build_external_source_asset
from teamster.kippcamden import CODE_LOCATION, deanslist, edplan, powerschool, titan

dbt_assets = build_dbt_assets(code_location=CODE_LOCATION)

external_source_assets = [
    build_external_source_asset(
        code_location=CODE_LOCATION,
        name=f"src_{asset.key.path[1]}__{asset.key.path[-1]}",
        dbt_package_name=asset.key.path[1],
        upstream_asset_key=asset.key,
        group_name=asset.key.path[1],
    )
    for asset in [*powerschool.assets, *deanslist.assets, *edplan.assets, *titan.assets]
]

__all__ = [
    dbt_assets,
    *external_source_assets,
]
