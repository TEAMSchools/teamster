import pathlib
from urllib.parse import ParseResult

from dagster import OpExecutionContext, asset

# from dagster_dbt import DbtCliResource
from google.cloud import bigquery

from teamster.kippcamden.powerschool.db.assets import assignments_assets

assignmentcategoryassoc = assignments_assets[0]


@asset(
    key_prefix=["kippcamden", "dbt", "powerschool"]
    # partitions_def=HourlyPartitionsDefinition(
    #     start_date=PS_PARTITION_START_DATE,
    #     timezone=LOCAL_TIME_ZONE.name,
    #     fmt="%Y-%m-%dT%H:%M:%S.%f",
    # )
    # required_resource_keys={"bq", "dbt"}
)
def assignmentcategoryassoc_dbt(
    context: OpExecutionContext, assignmentcategoryassoc: ParseResult
):
    context.log.info(assignmentcategoryassoc)
    file_path = pathlib.Path(assignmentcategoryassoc.path)

    code_location = file_path[2]
    schema_name = file_path[3]
    table_name = file_path[4]
    context.log.info(code_location)
    context.log.info(schema_name)
    context.log.info(table_name)

    # create BigQuery dataset, if not exists
    # bq: bigquery.Client = context.resources.bq
    # bq.create_dataset(dataset=f"{code_location}_{schema_name}", exists_ok=True)

    # # 3. dbt run-operation stage_external_sources
    # dbt: DbtCliResource = context.resources.dbt
    # dbt.run_operation(
    #     macro="stage_external_sources",
    #     args={
    #         "vars": "ext_full_refresh: true",
    #         "args": f"select: {code_location}_{schema_name}.{table_name}",
    #     },
    # )

    # 4. run merge using partition key
