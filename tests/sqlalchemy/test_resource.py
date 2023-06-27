from dagster import build_resources
from dagster_gcp import BigQueryResource
from google.cloud import bigquery

from teamster.kipptaf import GCS_PROJECT_NAME


def test_resource():
    with build_resources(
        resources={"db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME)}
    ) as resources:
        db_bigquery: bigquery.Client = next(resources.db_bigquery)

        query_job = db_bigquery.query(
            query="""
                SELECT
                CONCAT(
                    'https://stackoverflow.com/questions/',
                    CAST(id as STRING)) as url,
                view_count
                FROM `bigquery-public-data.stackoverflow.posts_questions`
                WHERE tags like '%google-bigquery%'
                ORDER BY view_count DESC
                LIMIT 10
            """
        )

        result = query_job.result()

        data = [dict(row) for row in result]

        print(data)
