from dagster import AssetKey, FreshnessPolicy

from teamster.libraries.finalsite.api.assets import CONTACTS_STAGING_FRESHNESS_POLICY

policies: dict[AssetKey, FreshnessPolicy] = {
    AssetKey(
        ["kippmiami", "finalsite", "stg_finalsite__contacts"]
    ): CONTACTS_STAGING_FRESHNESS_POLICY,
}
