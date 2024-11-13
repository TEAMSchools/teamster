from dagster import AssetExecutionContext
from dagster_embedded_elt.dlt import DagsterDltResource, dlt_assets
from dlt import pipeline
from dlt.sources.sql_database import sql_database


@dlt_assets(
    dlt_source=sql_database(
        schema="dna_assessments",
        table_names=["assessments", "agg_student_responses_standard"],
        defer_table_reflect=True,
    ),
    dlt_pipeline=pipeline(
        pipeline_name="illuminate",
        destination="bigquery",
        dataset_name="dlt_illuminate",
        progress="log",
    ),
)
def illuminate_assets(context: AssetExecutionContext, dlt: DagsterDltResource):
    yield from dlt.run(context=context)


assets = [
    illuminate_assets,
]
