import pathlib
from urllib.parse import ParseResult

from dagster import HourlyPartitionsDefinition, OpExecutionContext, Output, asset
from dagster_dbt import DbtCliResource, load_assets_from_dbt_project
from dagster_dbt.utils import generate_materializations
from google.cloud import bigquery

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippcamden import PS_PARTITION_START_DATE
from teamster.kippcamden.powerschool.db.assets import assignments_assets

dbt_assets = load_assets_from_dbt_project(
    project_dir="teamster-dbt",
    profiles_dir="teamster-dbt",
    key_prefix="dbt",
    source_key_prefix="dbt",
)

assignmentcategoryassoc = assignments_assets[0]


@asset(
    key_prefix=["kippcamden", "dbt", "powerschool"],
    partitions_def=HourlyPartitionsDefinition(
        start_date=PS_PARTITION_START_DATE,
        timezone=LOCAL_TIME_ZONE.name,
        fmt="%Y-%m-%dT%H:%M:%S.%f",
    ),
    required_resource_keys={"warehouse_bq", "dbt"},
)
def assignmentcategoryassoc(
    context: OpExecutionContext, assignmentcategoryassoc: ParseResult
):
    context.log.debug(assignmentcategoryassoc.geturl())

    file_path_parts = pathlib.Path(assignmentcategoryassoc.path).parts

    code_location = file_path_parts[2]
    schema_name = file_path_parts[3]
    table_name = file_path_parts[4]

    dataset = f"{code_location}_{schema_name}"

    # create BigQuery dataset, if not exists
    bq: bigquery.Client = context.resources.warehouse_bq
    context.log.debug(f"Creating dataset {dataset}")
    bq.create_dataset(dataset=dataset, exists_ok=True)

    # dbt run-operation stage_external_sources
    dbt: DbtCliResource = context.resources.dbt

    dbt_output = dbt.run_operation(
        macro="stage_external_sources",
        args={"select": f"{dataset}.{table_name}"},
        vars={"ext_full_refresh": True},
    )

    # yield materializations
    for materialization in generate_materializations(dbt_output):
        yield Output(materialization)
