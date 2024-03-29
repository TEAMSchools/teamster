from dagster import RunConfig, define_asset_job, job

from .... import CODE_LOCATION
from ....google.bigquery.ops import BigQueryGetTableOpConfig, bigquery_get_table_op
from .assets import workers
from .ops import adp_wfn_update_workers_op


@job(
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_adp_workforce_now__worker_update",
            )
        }
    ),
    tags={"job_type": "op"},
)
def adp_wfn_update_workers_job():
    worker_data = bigquery_get_table_op()

    adp_wfn_update_workers_op(worker_data)


adp_wfn_api_workers_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_workforce_now_api_workers_asset_job", selection=[workers]
)

_all = [
    adp_wfn_update_workers_job,
    adp_wfn_api_workers_asset_job,
]
