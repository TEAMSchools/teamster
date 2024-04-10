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

from teamster.core.deanslist.resources import DeansListResource
from teamster.core.deanslist.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYear, FiscalYearPartitionsDefinition
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)


def build_deanslist_static_partition_asset(
    code_location,
    asset_name,
    api_version,
    partitions_def: StaticPartitionsDefinition | None = None,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    asset_key = [code_location, "deanslist", asset_name.replace("-", "_")]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        compute_kind="deanslist",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        endpoint_content = deanslist.get(
            api_version=api_version,
            endpoint=asset_name,
            school_id=int(context.partition_key),
            params=params,
        )

        data = endpoint_content["data"]
        schema = ASSET_FIELDS[asset_name]

        yield Output(
            value=(data, schema), metadata={"records": endpoint_content["row_count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset


def build_deanslist_multi_partition_asset(
    code_location,
    asset_name,
    api_version,
    partitions_def: MultiPartitionsDefinition,
    op_tags: dict | None = None,
    params: dict | None = None,
) -> AssetsDefinition:
    if params is None:
        params = {}

    asset_key = [code_location, "deanslist", asset_name.replace("-", "_")]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        compute_kind="deanslist",
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
            endpoint=asset_name,
            school_id=int(partition_keys_by_dimension["school"]),
            params=request_params,
        )

        data = endpoint_content["data"]
        schema = ASSET_FIELDS[asset_name]

        yield Output(
            value=(data, schema), metadata={"records": endpoint_content["row_count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
