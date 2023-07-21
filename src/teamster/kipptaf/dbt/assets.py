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
from teamster.kipptaf.google.assets import google_forms_assets, google_sheets_assets

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

external_source_assets = [
    build_external_source_asset(
        code_location=CODE_LOCATION,
        name=f"src_{asset.key.path[1]}__{asset.key.path[-1]}",
        dbt_package_name=asset.key.path[1],
        upstream_asset_key=asset.key,
        group_name=asset.key.path[1],
    )
    for asset in [
        *achieve3k.assets,
        *adp.assets,
        *alchemer.assets,
        *amplify.assets,
        *clever.assets,
        *google_forms_assets,
        *iready.assets,
        *ldap.assets,
        *renlearn.assets,
        *schoolmint.assets,
        *smartrecruiters.assets,
    ]
]

__all__ = [
    dbt_assets,
    *gsheet_external_source_assets,
    *external_source_assets,
]
