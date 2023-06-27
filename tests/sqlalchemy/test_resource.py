import pendulum
from dagster import build_resources
from dagster_gcp import BigQueryResource
from google.cloud import bigquery

from teamster.core.datagun.assets import construct_query
from teamster.kipptaf import GCS_PROJECT_NAME

QUERY = {
    "query_type": "schema",
    "query_value": {
        "table": {"name": "rpt_idauto__staff_roster", "schema": "kipptaf_extracts"},
    },
}


def test_resource():
    with build_resources(
        resources={"db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME)}
    ) as resources:
        db_bigquery: bigquery.Client = next(resources.db_bigquery)

        query = construct_query(now=pendulum.now(), **QUERY)
        print(query)

        query_job = db_bigquery.query(query=str(query))

        result = query_job.result()

        data = [dict(row) for row in result]

        print(data)
