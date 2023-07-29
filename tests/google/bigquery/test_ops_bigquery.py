from dagster import build_op_context
from dagster_gcp import BigQueryResource

from teamster.core.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.kipptaf import GCS_PROJECT_NAME


def test_op():
    context = build_op_context()

    data = bigquery_get_table_op(
        context=context,
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
        config=BigQueryGetTableOpConfig(
            project="bigquery-public-data",
            dataset_id="country_codes",
            table_id="country_codes",
        ),
    )

    context.log.info(data)
