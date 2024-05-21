import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from teamster.core.utils.classes import FiscalYear, FiscalYearPartitionsDefinition
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.deanslist.resources import DeansListResource


def build_deanslist_static_partition_asset(
    asset_key,
    api_version,
    endpoint,
    schema,
    partitions_def: StaticPartitionsDefinition | None = None,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        compute_kind="python",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        endpoint_content = deanslist.get(
            api_version=api_version,
            endpoint=endpoint,
            school_id=int(context.partition_key),
            params=params,
        )

        data = endpoint_content["data"]

        yield Output(
            value=(data, schema), metadata={"records": endpoint_content["row_count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset


def build_deanslist_multi_partition_asset(
    asset_key,
    api_version,
    endpoint,
    schema,
    partitions_def: MultiPartitionsDefinition,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        compute_kind="python",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        partitions_def: MultiPartitionsDefinition = context.assets_def.partitions_def  # type: ignore
        partition_keys_by_dimension = context.partition_key.keys_by_dimension  # type: ignore

        date_partition_def = partitions_def.get_partitions_def_for_dimension("date")
        date_partition_key = pendulum.from_format(
            string=partition_keys_by_dimension["date"], fmt="YYYY-MM-DD"
        )

        request_params = {"UpdatedSince": date_partition_key.to_date_string(), **params}

        date_partition_key_fy = FiscalYear(datetime=date_partition_key, start_month=7)

        request_params["StartDate"] = date_partition_key_fy.start.to_date_string()

        if isinstance(date_partition_def, MonthlyPartitionsDefinition):
            request_params["EndDate"] = date_partition_key.end_of(
                "month"
            ).to_date_string()
        elif isinstance(date_partition_def, FiscalYearPartitionsDefinition):
            request_params["EndDate"] = date_partition_key_fy.end.to_date_string()

        endpoint_content = deanslist.get(
            api_version=api_version,
            endpoint=endpoint,
            school_id=int(partition_keys_by_dimension["school"]),
            params=request_params,
        )

        data = endpoint_content["data"]
        row_count = endpoint_content["row_count"]

        yield Output(value=(data, schema), metadata={"records": row_count})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
