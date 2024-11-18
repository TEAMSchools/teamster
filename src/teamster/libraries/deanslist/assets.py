import calendar
import re
from datetime import datetime

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    _check,
    asset,
)

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.core.utils.classes import FiscalYear, FiscalYearPartitionsDefinition
from teamster.libraries.deanslist.resources import DeansListResource


def build_deanslist_static_partition_asset(
    code_location: str,
    endpoint: str,
    api_version: str,
    schema,
    partitions_def: StaticPartitionsDefinition | None = None,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    asset_key = [
        code_location,
        "deanslist",
        re.sub(pattern=r"\W", repl="_", string=endpoint),
    ]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        total_count, data = deanslist.get(
            api_version=api_version,
            endpoint=endpoint,
            school_id=int(context.partition_key),
            params=params,
        )

        yield Output(value=(data, schema), metadata={"records": total_count})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset


def build_deanslist_multi_partition_asset(
    code_location: str,
    endpoint: str,
    api_version: str,
    schema,
    partitions_def: MultiPartitionsDefinition,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    asset_key = [
        code_location,
        "deanslist",
        re.sub(pattern=r"\W", repl="_", string=endpoint),
    ]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        partitions_def = _check.inst(
            obj=context.assets_def.partitions_def, ttype=MultiPartitionsDefinition
        )
        partition_key = _check.inst(obj=context.partition_key, ttype=MultiPartitionKey)

        date_partition_def = partitions_def.get_partitions_def_for_dimension("date")
        date_partition_key = datetime.fromisoformat(
            partition_key.keys_by_dimension["date"]
        )

        date_partition_key_fy = FiscalYear(datetime=date_partition_key, start_month=7)

        request_params = {
            "UpdatedSince": date_partition_key.date().isoformat(),
            "StartDate": date_partition_key_fy.start.isoformat(),
            **params,
        }

        if isinstance(date_partition_def, MonthlyPartitionsDefinition):
            _, last_day = calendar.monthrange(
                year=date_partition_key.year, month=date_partition_key.month
            )

            request_params["EndDate"] = (
                date_partition_key.replace(day=last_day).date().isoformat()
            )
        elif isinstance(date_partition_def, FiscalYearPartitionsDefinition):
            request_params["EndDate"] = date_partition_key_fy.end.isoformat()

        total_count, data = deanslist.get(
            api_version=api_version,
            endpoint=endpoint,
            school_id=int(partition_key.keys_by_dimension["school"]),
            params=request_params,
        )

        yield Output(value=(data, schema), metadata={"records": total_count})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset


def build_deanslist_paginated_multi_partition_asset(
    code_location: str,
    endpoint: str,
    api_version: str,
    schema,
    partitions_def: MultiPartitionsDefinition,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    asset_key = [code_location, "deanslist", "behavior"]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        partition_key = _check.inst(obj=context.partition_key, ttype=MultiPartitionKey)

        date_partition_key = datetime.fromisoformat(
            partition_key.keys_by_dimension["date"]
        )

        date_partition_key_fy = FiscalYear(datetime=date_partition_key, start_month=7)

        total_count, data = deanslist.list(
            api_version=api_version,
            endpoint=endpoint,
            school_id=int(partition_key.keys_by_dimension["school"]),
            params={
                "UpdatedSince": date_partition_key.date().isoformat(),
                "StartDate": date_partition_key_fy.start.isoformat(),
                "EndDate": date_partition_key_fy.end.isoformat(),
                **params,
            },
        )

        yield Output(value=(data, schema), metadata={"records": total_count})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
