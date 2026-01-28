from datetime import timedelta

from dagster import AssetKey, build_last_update_freshness_checks

from teamster.code_locations.kippnewark import LOCAL_TIMEZONE

titan_asset_selection = [
    AssetKey(["kippnewark", "titan", "person_data"]),
    AssetKey(["kippnewark", "titan", "stg_titan__person_data"]),
]

titan_freshness_checks = build_last_update_freshness_checks(
    assets=titan_asset_selection,
    lower_bound_delta=timedelta(minutes=30),
    deadline_cron="30 23 * * *",
    timezone=str(LOCAL_TIMEZONE),
)

freshness_checks = [
    *titan_freshness_checks,
]
