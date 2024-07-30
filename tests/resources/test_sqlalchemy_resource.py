from dagster import build_resources
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import Client as BigQueryClient

from teamster import GCS_PROJECT_NAME
from teamster.libraries.datagun.assets import construct_query


def _test(query_type, query_value):
    with build_resources(
        resources={"db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME)}
    ) as resources:
        db_bigquery: BigQueryClient = next(resources.db_bigquery)

    query = construct_query(query_type=query_type, query_value=query_value)
    print(query)

    query_job = db_bigquery.query(query=str(query))

    result = query_job.result()

    data = [dict(row) for row in result]

    print(data)


def test_schema_query():
    table_schema = "kipptaf_extracts"
    table_name = "rpt_deanslist__mod_assessment"

    _test(
        query_type="schema",
        query_value={"table": {"name": table_name, "schema": table_schema}},
    )
