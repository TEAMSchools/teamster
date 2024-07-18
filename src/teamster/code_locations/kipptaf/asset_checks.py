from datetime import timedelta

from dagster import AssetSelection, build_last_update_freshness_checks

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._dbt.assets import (
    dbt_assets,
    external_source_dbt_assets,
)
from teamster.code_locations.kipptaf.fivetran.assets import adp_workforce_now_assets

dbt_asset_selection = AssetSelection.assets(
    dbt_assets, external_source_dbt_assets
).key_prefixes([CODE_LOCATION, "adp_workforce_now"])

asset1_freshness_checks = build_last_update_freshness_checks(
    assets=[*adp_workforce_now_assets, *dbt_asset_selection],
    lower_bound_delta=timedelta(hours=2),
)
