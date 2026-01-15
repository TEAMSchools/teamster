from dagster import Config, OpExecutionContext, op
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import DatasetReference


class BigQueryOpConfig(Config):
    dataset_id: str = ""
    table_id: str = ""
    query: str | None = None
    project: str | None = None


@op
def bigquery_get_table_op(
    context: OpExecutionContext, db_bigquery: BigQueryResource, config: BigQueryOpConfig
):
    project = config.project or db_bigquery.project

    dataset_ref = DatasetReference(
        project=(project or ""), dataset_id=config.dataset_id
    )

    table_ref = dataset_ref.table(table_id=config.table_id)

    context.log.info(msg=f"Getting table: {table_ref}")

    with db_bigquery.get_client() as bq:
        table = bq.get_table(table=table_ref)

        rows = bq.list_rows(table=table)

    context.log.info(msg=f"Retrieved {rows.total_rows} rows")
    arrow = rows.to_arrow()

    return arrow.to_pylist()


@op
def bigquery_query_op(
    context: OpExecutionContext, db_bigquery: BigQueryResource, config: BigQueryOpConfig
):
    project = config.project or db_bigquery.project

    if config.query is not None:
        query = config.query
    else:
        # trunk-ignore(bandit/B608)
        query = f"select * from {config.dataset_id}.{config.table_id}"

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")

    return arrow.to_pylist()
