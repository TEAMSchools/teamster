import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MultiPartitionsDefinition,
    Output,
    asset,
)

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.schoolmint.grow.resources import SchoolMintGrowResource


def build_schoolmint_grow_asset(asset_key, partitions_def, schema) -> AssetsDefinition:
    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="schoolmint",
        compute_kind="python",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, schoolmint_grow: SchoolMintGrowResource):
        if isinstance(context.assets_def.partitions_def, MultiPartitionsDefinition):
            keys_by_dimension = context.partition_key.keys_by_dimension  # type: ignore

            archived_partition = keys_by_dimension["archived"]
            last_modified_partition = (
                pendulum.from_format(
                    string=keys_by_dimension["last_modified"], fmt="YYYY-MM-DD"
                )
                .subtract(days=1)
                .timestamp()
            )
        else:
            archived_partition = context.partition_key
            last_modified_partition = None

        # TODO: lastModified == None for first partition

        endpoint_content = schoolmint_grow.get(
            endpoint=context.asset_key.path[-1],
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
