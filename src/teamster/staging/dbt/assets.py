from teamster.core.dbt.assets import build_dbt_assets, build_dbt_external_source_assets

from .. import CODE_LOCATION

dbt_assets = build_dbt_assets(code_location=CODE_LOCATION)
dbt_external_source_assets = build_dbt_external_source_assets(
    code_location=CODE_LOCATION
)

__all__ = [
    dbt_assets,
    dbt_external_source_assets,
]
