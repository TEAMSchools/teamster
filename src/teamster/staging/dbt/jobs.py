from dagster import AssetSelection, define_asset_job

from teamster.kipptaf.dbt.assets import dbt_assets

dbt_adp_wfm_asset_job = define_asset_job(
    name="dbt_adp_wfm_asset_job",
    selection=(
        AssetSelection.assets(dbt_assets)
        & AssetSelection.key_prefixes(["kipptaf", "adp_workforce_now"])
    ),
)

__all__ = [
    dbt_adp_wfm_asset_job,
]
