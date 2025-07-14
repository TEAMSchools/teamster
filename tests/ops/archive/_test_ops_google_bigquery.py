"""from dagster import build_op_context
from dagster_gcp import BigQueryResource

from teamster import GCS_PROJECT_NAME
from teamster.libraries.google.bigquery.ops import (
    BigQueryOpConfig,
    bigquery_get_table_op,
    bigquery_query_op,
)


def test_bigquery_get_table_op():
    context = build_op_context()

    data = bigquery_get_table_op(
        context=context,
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
        config=BigQueryOpConfig(
            project="bigquery-public-data",
            dataset_id="country_codes",
            table_id="country_codes",
        ),
    )

    context.log.info(data)


def test_bigquery_query_op():
    context = build_op_context()

    data = bigquery_query_op(
        context=context,
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
        config=BigQueryOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
        ),
    )

    context.log.info(data)
"""
