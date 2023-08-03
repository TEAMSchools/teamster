from dagster import AssetSelection, RunConfig, define_asset_job, job

from teamster.core.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)

from .. import CODE_LOCATION
from .assets import wfm_assets_daily, wfm_assets_dynamic
from .ops import adp_wfn_update_workers_op

daily_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_daily_partition_asset_job",
    selection=AssetSelection.assets(*wfm_assets_daily),
    partitions_def=wfm_assets_daily[0].partitions_def,
)

dynamic_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_dynamic_partition_asset_job",
    selection=AssetSelection.assets(*wfm_assets_dynamic),
    partitions_def=wfm_assets_dynamic[0].partitions_def,
)


@job(
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id=f"{CODE_LOCATION}_extracts",
                table_id="rpt_adp_workforce_now__worker_update",
            )
        }
    )
)
def adp_wfn_update_workers_job():
    worker_data = bigquery_get_table_op()

    adp_wfn_update_workers_op(worker_data)


__all__ = [
    daily_partition_asset_job,
    dynamic_partition_asset_job,
    adp_wfn_update_workers_job,
]
