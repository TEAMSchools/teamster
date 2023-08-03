from teamster.core.dbt.assets import build_dbt_assets, build_external_source_asset
from teamster.kipptaf import (
    CODE_LOCATION,
    achieve3k,
    adp,
    alchemer,
    amplify,
    clever,
    iready,
    ldap,
    renlearn,
    schoolmint,
    smartrecruiters,
)
from teamster.kipptaf.google.assets import (
    google_directory_assets,
    google_forms_assets,
    google_sheets_assets,
)

dbt_assets = build_dbt_assets(code_location=CODE_LOCATION)

gsheet_external_source_assets = [
    build_external_source_asset(
        code_location=CODE_LOCATION,
        name="src_" + asset.key.path[-1],
        dbt_package_name=asset.key.path[-1].split("__")[0],
        upstream_asset_key=asset.key,
        group_name=asset.key.path[-1].split("__")[0],
    )
    for asset in google_sheets_assets
]

external_source_assets = []
for asset in [
    *achieve3k.assets,
    *adp.assets,
    *alchemer.assets,
    *amplify.assets,
    *clever.assets,
    *iready.assets,
    *ldap.assets,
    *renlearn.assets,
    *schoolmint.assets,
    *smartrecruiters.assets,
    *google_forms_assets,
    *google_directory_assets,
]:
    dbt_package_name = "_".join(asset.key.path[1:-1])

    external_source_assets.append(
        build_external_source_asset(
            code_location=CODE_LOCATION,
            name=f"src_{dbt_package_name}__{asset.key.path[-1]}",
            dbt_package_name=dbt_package_name,
            upstream_asset_key=asset.key,
            group_name=asset.key.path[1],
        )
    )

__all__ = [
    dbt_assets,
    *gsheet_external_source_assets,
    *external_source_assets,
]
