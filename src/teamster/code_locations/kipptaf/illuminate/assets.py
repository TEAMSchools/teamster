import json

from dagster import AssetExecutionContext, EnvVar, _check
from dagster_embedded_elt.dlt import DagsterDltResource, dlt_assets
from dlt import pipeline
from dlt.sources.sql_database import sql_database
from sqlalchemy import URL, create_engine


@dlt_assets(
    dlt_source=sql_database(
        credentials=create_engine(
            url=URL.create(
                drivername=_check.not_none(
                    value=EnvVar("ILLUMINATE_DB_DRIVERNAME").get_value()
                ),
                host=EnvVar("ILLUMINATE_DB_HOST").get_value(),
                database=EnvVar("ILLUMINATE_DB_DATABASE").get_value(),
                username=EnvVar("ILLUMINATE_DB_USERNAME").get_value(),
                password=EnvVar("ILLUMINATE_DB_PASSWORD").get_value(),
            )
        ),
        schema="dna_assessments",
        table_names=["assessments", "agg_student_responses_standard"],
        defer_table_reflect=True,
    ),
    dlt_pipeline=pipeline(
        pipeline_name="illuminate",
        destination="bigquery",
        dataset_name="dlt_illuminate_dna_assessments",
        progress="log",
    ),
)
def illuminate_dna_assessments(context: AssetExecutionContext, dlt: DagsterDltResource):
    yield from dlt.run(
        context=context,
        credentials=json.load(
            fp=open(file="/etc/secret-volume/gcloud_teamster_dlt_keyfile.json")
        ),
    )


assets = [
    illuminate_dna_assessments,
]
