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

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource


def build_schoolmint_grow_asset(
    asset_key, endpoint, partitions_def, schema, op_tags=None
) -> AssetsDefinition:
    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="schoolmint",
        compute_kind="python",
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        op_tags=op_tags,
    )
    def _asset(context: AssetExecutionContext, schoolmint_grow: SchoolMintGrowResource):
        if isinstance(context.assets_def.partitions_def, MultiPartitionsDefinition):
            partition_key = _check.inst(context.partition_key, MultiPartitionKey)

            archived_key = partition_key.keys_by_dimension["archived"]
            last_modified_start = (
                pendulum.from_format(
                    string=partition_key.keys_by_dimension["last_modified"],
                    fmt="YYYY-MM-DD",
                )
                .subtract(days=1)
                .timestamp()
            )

            last_modified_end = last_modified_start + 86400

            last_modified_def = (
                context.assets_def.partitions_def.get_partitions_def_for_dimension(
                    "last_modified"
                )
            )

            if (
                partition_key.keys_by_dimension["last_modified"]
                == last_modified_def.get_first_partition_key()
            ):
                last_modified_key = f"0,{last_modified_end}"
            elif (
                partition_key.keys_by_dimension["last_modified"]
                == last_modified_def.get_last_partition_key()
            ):
                last_modified_key = last_modified_start
            else:
                last_modified_key = f"{last_modified_start},{last_modified_end}"
        else:
            archived_key = context.partition_key
            last_modified_key = None

        endpoint_content = schoolmint_grow.get(
            endpoint=endpoint,
            archived=(archived_key == "t"),
            lastModified=last_modified_key,
        )

        records = endpoint_content["data"]

        yield Output(
            value=(records, schema), metadata={"records": endpoint_content["count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
