import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from teamster.core.deanslist.resources import DeansListResource
from teamster.core.deanslist.schema import ASSET_FIELDS
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_record_schema,
    get_avro_schema_valid_check_spec,
)


def build_deanslist_static_partition_asset(
    code_location,
    asset_name,
    api_version,
    partitions_def: StaticPartitionsDefinition | None = None,
    op_tags={},
    params={},
) -> AssetsDefinition:
    asset_key = [code_location, "deanslist", asset_name.replace("-", "_")]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
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
        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name][api_version]
        )

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
    op_tags={},
    params={},
) -> AssetsDefinition:
    asset_key = [code_location, "deanslist", asset_name.replace("-", "_")]

    @asset(
        key=asset_key,
        metadata=params,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name="deanslist",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, deanslist: DeansListResource):
        partitions_def: MultiPartitionsDefinition = context.assets_def.partitions_def  # type: ignore
        partition_key: MultiPartitionKey = context.partition_key  # type: ignore

        school_partition = partition_key.keys_by_dimension["school"]
        date_partition = pendulum.from_format(
            string=partition_key.keys_by_dimension["date"], fmt="YYYY-MM-DD"
        )

        request_params = {"UpdatedSince": date_partition.to_date_string(), **params}
        if isinstance(
            partitions_def.get_partitions_def_for_dimension("date"),
            MonthlyPartitionsDefinition,
        ):
            request_params["StartDate"] = date_partition.to_date_string()
            request_params["EndDate"] = date_partition.end_of("month").to_date_string()

        endpoint_content = deanslist.get(
            api_version=api_version,
            endpoint=asset_name,
            school_id=int(school_partition),
            params=request_params,
        )

        data = endpoint_content["data"]
        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name][api_version]
        )

        yield Output(
            value=(data, schema), metadata={"records": endpoint_content["row_count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
