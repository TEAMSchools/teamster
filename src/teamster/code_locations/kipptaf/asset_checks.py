from datetime import timedelta

from dagster import AssetKey, build_last_update_freshness_checks

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE

adp_wfn_asset_selection = [
    AssetKey(["kipptaf", "people", "int_people__staff_roster"]),
    AssetKey(["kipptaf", "people", "int_people__staff_roster_history"]),
    AssetKey(["kipptaf", "people", "stg_people__employee_numbers"]),
    AssetKey(["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__workers"]),
    AssetKey(
        [
            "kipptaf",
            "adp_workforce_now",
            "stg_adp_workforce_now__workers__work_assignments",
        ]
    ),
    AssetKey(
        [
            "kipptaf",
            "adp_workforce_now",
            "stg_adp_workforce_now__workers__work_assignments__reports_to",
        ]
    ),
]

adp_wfn_freshness_checks = build_last_update_freshness_checks(
    assets=adp_wfn_asset_selection,
    lower_bound_delta=timedelta(minutes=45),
    deadline_cron="15 1 * * *",
    timezone=str(LOCAL_TIMEZONE),
)

freshness_checks = [
    *adp_wfn_freshness_checks,
]
