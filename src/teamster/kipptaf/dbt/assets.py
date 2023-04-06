from teamster.core.dbt.assets import build_external_source_asset

from .. import schoolmint

dbt_src_assets = [build_external_source_asset(a) for a in [*schoolmint.assets.__all__]]

__all__ = [
    *dbt_src_assets,
]
