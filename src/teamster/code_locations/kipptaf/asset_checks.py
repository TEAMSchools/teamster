from datetime import timedelta

from dagster import AssetKey, build_last_update_freshness_checks

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE

adp_wfn_asset_selection = [
    AssetKey(["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__workers"]),
    AssetKey(["kipptaf", "people", "stg_people__employee_numbers"]),
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
    AssetKey(
        [
            "kipptaf",
            "adp_workforce_now",
            "int_adp_workforce_now_assignments__organizational_units__pivot",
        ]
    ),
]

adp_wfn_freshness_checks = build_last_update_freshness_checks(
    assets=adp_wfn_asset_selection,
    lower_bound_delta=timedelta(minutes=45),
    deadline_cron="15 1 * * *",
    timezone=LOCAL_TIMEZONE.name,
)

freshness_checks = [
    *adp_wfn_freshness_checks,
]
