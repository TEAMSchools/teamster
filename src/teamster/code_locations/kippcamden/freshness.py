from datetime import timedelta

from dagster import AssetKey, FreshnessPolicy

from teamster.code_locations.kippcamden import LOCAL_TIMEZONE

titan_policy = FreshnessPolicy.cron(
    deadline_cron="30 23 * * *",
    lower_bound_delta=timedelta(minutes=30),
    timezone=str(LOCAL_TIMEZONE),
)

policies: dict[AssetKey, FreshnessPolicy] = {
    AssetKey(["kippcamden", "titan", "person_data"]): titan_policy,
    AssetKey(["kippcamden", "titan", "stg_titan__person_data"]): titan_policy,
}
