from dagster import InputContext, OpExecutionContext, asset
from dagster_dbt import DbtCliResource
from google.cloud import bigquery


@asset(required_resource_keys={"bq", "dbt"})
def dbt_external_table_asset(
    context: OpExecutionContext, upstream_output: InputContext
):
    upstream_output.partition_key
    # 1. parse input asset
    code_location = ""
    asset_key = []
    schema_name = asset_key[0]
    table_name = asset_key[-1]
    # partition_key = ""

    # 2. create dataset, if not exists
    bq: bigquery.Client = context.resources.bq
    bq.create_dataset(dataset=f"{code_location}_{schema_name}", exists_ok=True)

    # 3. dbt run-operation stage_external_sources
    dbt: DbtCliResource = context.resources.dbt
    dbt.run_operation(
        macro="stage_external_sources",
        args={
            "vars": "ext_full_refresh: true",
            "args": f"select: {code_location}_{schema_name}.{table_name}",
        },
    )

    # 4. run merge using partition key
