from teamster.core.dbt.assets import build_external_source_asset

from .. import alchemer, schoolmint

dbt_src_assets = [
    build_external_source_asset(a) for a in [*schoolmint.assets, *alchemer.assets]
]

__all__ = [
    *dbt_src_assets,
]
