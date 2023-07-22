import pendulum
from dagster import build_resources
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import Client


def render_fivetran_audit_query(dataset, done):
    return f"""
        select distinct table
        from {dataset}.fivetran_audit
        where done >= '{done}'
    """


def test_resource():
    today = pendulum.now().start_of(unit="day")

    with build_resources(
        resources={"db_bigquery": BigQueryResource(project="teamster-332318")}
    ) as resources:
        db_bigquery: Client = next(resources.db_bigquery)

        query_job = db_bigquery.query(
            query=render_fivetran_audit_query(
                dataset="coupa", done=today.to_iso8601_string()
            )
        )

        for row in query_job.result():
            print(row.table)
