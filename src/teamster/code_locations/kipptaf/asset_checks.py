from datetime import timedelta

from dagster import AssetKey, build_last_update_freshness_checks

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.fivetran.assets import adp_workforce_now_assets

adp_wfn_dbt_asset_selection = [
    AssetKey(["kipptaf", "adp_workforce_now", "int_adp_workforce_now__person"]),
    AssetKey(["kipptaf", "adp_workforce_now", "int_adp_workforce_now__worker"]),
    AssetKey(["kipptaf", "adp_workforce_now", "int_adp_workforce_now__worker_person"]),
    AssetKey(["kipptaf", "adp_workforce_now", "src_adp_workforce_now__workers"]),
    AssetKey(["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__person_history"]),
    AssetKey(["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__person_history"]),
    AssetKey(["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__workers"]),
    AssetKey(["kipptaf", "people", "stg_people__employee_numbers"]),
    AssetKey(
        [
            "kipptaf",
            "adp_workforce_now",
            "stg_adp_workforce_now__person_communication_pivot",
        ],
    ),
    AssetKey(
        [
            "kipptaf",
            "adp_workforce_now",
            "stg_adp_workforce_now__person_preferred_salutation_pivot",
        ]
    ),
    AssetKey(
        [
            "kipptaf",
            "adp_workforce_now",
            "stg_adp_workforce_now__worker_organizational_unit_pivot",
        ]
    ),
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
    assets=[*adp_workforce_now_assets, *adp_wfn_dbt_asset_selection],
    lower_bound_delta=timedelta(hours=4, minutes=30),
    deadline_cron="30 4 * * *",
    timezone=LOCAL_TIMEZONE.name,
)

freshness_checks = [
    *adp_wfn_freshness_checks,
]
