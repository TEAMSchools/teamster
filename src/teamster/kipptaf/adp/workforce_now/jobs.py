from dagster import RunConfig, job

from ...google.bigquery.ops import BigQueryGetTableOpConfig, bigquery_get_table_op
from .ops import adp_wfn_update_workers_op


@job(
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_adp_workforce_now__worker_update",
            )
        }
    )
)
def adp_wfn_update_workers_job():
    worker_data = bigquery_get_table_op()

    adp_wfn_update_workers_op(worker_data)


__all__ = [
    adp_wfn_update_workers_job,
]
