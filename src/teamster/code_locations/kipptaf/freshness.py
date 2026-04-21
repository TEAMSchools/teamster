from datetime import timedelta

from dagster import AssetKey, FreshnessPolicy

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE

adp_wfn_policy = FreshnessPolicy.cron(
    deadline_cron="15 1 * * *",
    lower_bound_delta=timedelta(minutes=45),
    timezone=str(LOCAL_TIMEZONE),
)

policies: dict[AssetKey, FreshnessPolicy] = {
    AssetKey(["kipptaf", "people", "int_people__staff_roster"]): adp_wfn_policy,
    AssetKey(["kipptaf", "people", "int_people__staff_roster_history"]): adp_wfn_policy,
    AssetKey(["kipptaf", "people", "stg_people__employee_numbers"]): adp_wfn_policy,
    AssetKey(
        ["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__workers"]
    ): adp_wfn_policy,
}
