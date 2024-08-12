from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.adp.workforce_now.api.ops import adp_wfn_update_workers_op
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)


@job(
    name=f"{CODE_LOCATION}_adp_wfn_update_workers_job",
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
