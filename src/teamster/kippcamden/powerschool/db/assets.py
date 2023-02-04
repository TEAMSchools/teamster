import pathlib
from urllib.parse import ParseResult

from dagster import (
    HourlyPartitionsDefinition,
    OpExecutionContext,
    Output,
    asset,
    config_from_files,
)
from dagster_dbt import DbtCliResource
from dagster_dbt.utils import generate_materializations
from google.cloud import bigquery

from teamster.core.powerschool.db.assets import build_powerschool_table_asset
from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippcamden import CODE_LOCATION, PS_PARTITION_START_DATE

nonpartition_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-nonpartition.yaml"]
    )["assets"]
]

transactiondate_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=PS_PARTITION_START_DATE,
        where_column="transaction_date",
    )
    for cfg in config_from_files(
        [
            f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-transactiondate.yaml"
        ]
    )["assets"]
]

assignments_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=PS_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-assignments.yaml"]
    )["assets"]
]

contacts_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=PS_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-contacts.yaml"]
    )["assets"]
]

extensions_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=PS_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-extensions.yaml"]
    )["assets"]
]

whenmodified_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=PS_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-whenmodified.yaml"]
    )["assets"]
]


assignmentcategoryassoc = assignments_assets[0]


@asset(
    name="src_assignmentcategoryassoc",
    key_prefix=["kippcamden_powerschool"],
    partitions_def=HourlyPartitionsDefinition(
        start_date=PS_PARTITION_START_DATE,
        timezone=LOCAL_TIME_ZONE.name,
        fmt="%Y-%m-%dT%H:%M:%S.%f",
    ),
    required_resource_keys={"warehouse_bq", "dbt"},
)
def src_assignmentcategoryassoc(
    context: OpExecutionContext, assignmentcategoryassoc: ParseResult
):
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
        args={"select": f"{dataset}.src_{table_name}"},
        vars={"ext_full_refresh": True},
    )

    # yield materializations
    for materialization in generate_materializations(dbt_output):
        yield Output(materialization)
