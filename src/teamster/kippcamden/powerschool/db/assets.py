from dagster import (
    HourlyPartitionsDefinition,
    InputContext,
    OpExecutionContext,
    asset,
    config_from_files,
)

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
    # partitions_def=HourlyPartitionsDefinition(
    #     start_date=PS_PARTITION_START_DATE,
    #     timezone=LOCAL_TIME_ZONE.name,
    #     fmt="%Y-%m-%dT%H:%M:%S.%f",
    # )
    # required_resource_keys={"bq", "dbt"}
)
def dbt_external_table_asset(
    context: OpExecutionContext, assignmentcategoryassoc: InputContext
):
    context.log.info(assignmentcategoryassoc.name)
    context.log.info(assignmentcategoryassoc.asset_key)
    try:
        context.log.info(assignmentcategoryassoc.partition_key)
    except:
        pass
    try:
        context.log.info(assignmentcategoryassoc.get_asset_identifier())
    except:
        pass

    # # 1. parse input asset
    # code_location = ""
    # asset_key = []
    # schema_name = asset_key[0]
    # table_name = asset_key[-1]
    # partition_key = ""

    # # 2. create dataset, if not exists
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
