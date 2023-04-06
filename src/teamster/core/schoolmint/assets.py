import pendulum
from dagster import (
    AssetsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from teamster.core.schoolmint.resources import Grow
from teamster.core.schoolmint.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema
from teamster.core.utils.variables import LOCAL_TIME_ZONE


def build_static_partition_asset(
    asset_name, code_location, partitions_def: StaticPartitionsDefinition, op_tags={}
) -> AssetsDefinition:
    @asset(
        name=asset_name.replace("-", "_").replace("/", "_"),
        key_prefix=[code_location, "schoolmint", "grow"],
        partitions_def=partitions_def,
        op_tags=op_tags,
        required_resource_keys={"schoolmint_grow"},
        io_manager_key="gcs_avro_io",
        output_required=False,
    )
    def _asset(context: OpExecutionContext):
        grow: Grow = context.resources.schoolmint_grow

        response = grow.get(
            endpoint=asset_name, archived=(context.partition_key == "t")
        )

        count = response["count"]

        if count > 0:
            yield Output(
                value=(
                    response["data"],
                    get_avro_record_schema(
                        name=asset_name, fields=ENDPOINT_FIELDS[asset_name]
                    ),
                ),
                metadata={"records": count},
            )

    return _asset


def build_multi_partition_asset(
    asset_name, code_location, partitions_def: MultiPartitionsDefinition, op_tags={}
) -> AssetsDefinition:
    @asset(
        name=asset_name.replace("-", "_").replace("/", "_"),
        key_prefix=[code_location, "schoolmint", "grow"],
        partitions_def=partitions_def,
        op_tags=op_tags,
        required_resource_keys={"schoolmint_grow"},
        io_manager_key="gcs_avro_io",
        output_required=False,
    )
    def _asset(context: OpExecutionContext):
        asset_key = context.asset_key_for_output()
        archived_partition = context.partition_key.keys_by_dimension["archived"]
        last_modified_partition = (
            pendulum.from_format(
                string=context.partition_key.keys_by_dimension["last_modified"],
                fmt="YYYY-MM-DD",
                tz=LOCAL_TIME_ZONE,
            )
            .subtract(days=1)
            .timestamp()
        )

        # check if static paritition has ever been materialized
        static_materialization_count = 0
        asset_materialization_counts = (
            context.instance.get_materialization_count_by_partition([asset_key]).get(
                asset_key, {}
            )
        )

        for partition_key, count in asset_materialization_counts.items():
            if archived_partition == partition_key.split("|")[0]:
                static_materialization_count += count

        if (
            static_materialization_count == 0
            or static_materialization_count == context.retry_number
        ):
            last_modified_partition = None

        grow: Grow = context.resources.schoolmint_grow

        endpoint_content = grow.get(
            endpoint=asset_name,
            archived=(archived_partition == "t"),
            lastModified=last_modified_partition,
        )

        count = endpoint_content["count"]

        if count > 0:
            yield Output(
                value=(
                    endpoint_content["data"],
                    get_avro_record_schema(
                        name=asset_name, fields=ENDPOINT_FIELDS[asset_name]
                    ),
                ),
                metadata={"records": count},
            )

    return _asset
