from dagster import Config, OpExecutionContext, op
from dagster_gcp import BigQueryResource
from google.cloud import bigquery
from pandas import DataFrame


class BigqueryGetTableOpConfig(Config):
    dataset_id: str
    table_id: str
    project: str = None


@op
def bigquery_get_table_op(
    context: OpExecutionContext,
    db_bigquery: BigQueryResource,
    config: BigqueryGetTableOpConfig,
):
    dataset_ref = bigquery.DatasetReference(
        project=(config.project or db_bigquery.project), dataset_id=config.dataset_id
    )

    with db_bigquery.get_client() as bq:
        bq = bq

    table_ref = dataset_ref.table(table_id=config.table_id)

    table = bq.get_table(table=table_ref)

    rows = bq.list_rows(table=table)

    df: DataFrame = rows.to_dataframe()

    return df.to_dict(orient="records")
