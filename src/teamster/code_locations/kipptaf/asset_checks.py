from datetime import timedelta

from dagster import AssetSelection, build_last_update_freshness_checks

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf._dbt.assets import (
    dbt_assets,
    external_source_dbt_assets,
)
from teamster.code_locations.kipptaf.fivetran.assets import adp_workforce_now_assets

adp_wfn_dbt_asset_selection = [
    a
    for a in AssetSelection.assets(dbt_assets, external_source_dbt_assets).selected_keys
    if a.has_prefix([CODE_LOCATION, "adp_workforce_now"])
]

adp_wfn_freshness_checks = build_last_update_freshness_checks(
    assets=[*adp_workforce_now_assets, *adp_wfn_dbt_asset_selection],
    lower_bound_delta=timedelta(hours=4),
    deadline_cron="0 4 * * *",
    timezone=LOCAL_TIMEZONE.name,
)

freshness_checks = [
    *adp_wfn_freshness_checks,
]
