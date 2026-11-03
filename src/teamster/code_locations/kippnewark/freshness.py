from datetime import timedelta

from dagster import AssetKey, FreshnessPolicy

from teamster.code_locations.kippnewark import LOCAL_TIMEZONE
from teamster.libraries.finalsite.api.assets import CONTACTS_STAGING_FRESHNESS_POLICY

titan_policy = FreshnessPolicy.cron(
    deadline_cron="0 1 * * *",
    lower_bound_delta=timedelta(hours=1),
    timezone=str(LOCAL_TIMEZONE),
)

policies: dict[AssetKey, FreshnessPolicy] = {
    AssetKey(["kippnewark", "titan", "person_data"]): titan_policy,
    AssetKey(["kippnewark", "titan", "stg_titan__person_data"]): titan_policy,
    AssetKey(
        ["kippnewark", "finalsite", "stg_finalsite__contacts"]
    ): CONTACTS_STAGING_FRESHNESS_POLICY,
}
