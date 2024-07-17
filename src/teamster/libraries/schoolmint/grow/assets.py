import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    _check,
    asset,
)

from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource


def build_schoolmint_grow_asset(
    asset_key, endpoint, partitions_def, schema
) -> AssetsDefinition:
    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="schoolmint",
        compute_kind="python",
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, schoolmint_grow: SchoolMintGrowResource):
        if isinstance(context.assets_def.partitions_def, MultiPartitionsDefinition):
            partition_key = _check.inst(context.partition_key, MultiPartitionKey)

            archived_partition = partition_key.keys_by_dimension["archived"]
            last_modified_partition = (
                pendulum.from_format(
                    string=partition_key.keys_by_dimension["last_modified"],
                    fmt="YYYY-MM-DD",
                )
                .subtract(days=1)
                .timestamp()
            )
        else:
            archived_partition = context.partition_key
            last_modified_partition = None

        # TODO: lastModified == None for first partition

        endpoint_content = schoolmint_grow.get(
            endpoint=endpoint,
            archived=(archived_partition == "t"),
            lastModified=last_modified_partition,
        )

        records = endpoint_content["data"]

        yield Output(
            value=(records, schema), metadata={"records": endpoint_content["count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
