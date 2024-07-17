from datetime import timedelta

from dagster import build_last_update_freshness_checks

from teamster.code_locations.kipptaf._dbt.assets import dbt_assets
from teamster.code_locations.kipptaf.fivetran.assets import adp_workforce_now_assets

dbt_assets.keys

asset1_freshness_checks = build_last_update_freshness_checks(
    assets=adp_workforce_now_assets, lower_bound_delta=timedelta(hours=2)
)
