import pendulum
from dagster import (
    AssetsDefinition,
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from teamster.core.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.core.schoolmint.grow.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["t", "f"])


# TODO: combine with partition type logic
def build_schoolmint_grow_static_partition_asset(
    asset_name, op_tags={}
) -> AssetsDefinition:
    @asset(
        key=["schoolmint", "grow", asset_name.replace("-", "_").replace("/", "_")],
        io_manager_key="io_manager_gcs_avro",
        partitions_def=STATIC_PARTITONS_DEF,
        op_tags=op_tags,
        group_name="schoolmint_grow",
    )
    def _asset(context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource):
        response = schoolmint_grow.get(
            endpoint=asset_name, archived=(context.partition_key == "t")
        )

        count = response["count"]

        yield Output(
            value=(
                response["data"],
                get_avro_record_schema(
                    name=asset_name, fields=ASSET_FIELDS[asset_name]
                ),
            ),
            metadata={"records": count},
        )

    return _asset


def build_schoolmint_grow_multi_partition_asset(
    asset_name, start_date, timezone, op_tags={}
) -> AssetsDefinition:
    @asset(
        key=["schoolmint", "grow", asset_name.replace("-", "_").replace("/", "_")],
        io_manager_key="io_manager_gcs_avro",
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "archived": STATIC_PARTITONS_DEF,
                "last_modified": DailyPartitionsDefinition(
                    start_date=start_date, timezone=timezone, end_offset=1
                ),
            }
        ),
        op_tags=op_tags,
        group_name="schoolmint_grow",
    )
    def _asset(context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource):
        archived_partition = context.partition_key.keys_by_dimension["archived"]
        last_modified_partition = (
            pendulum.from_format(
                string=context.partition_key.keys_by_dimension["last_modified"],
                fmt="YYYY-MM-DD",
            )
            .subtract(days=1)
            .timestamp()
        )

        # TODO: lastModified == None for first partition

        endpoint_content = schoolmint_grow.get(
            endpoint=asset_name,
            lastModified=last_modified_partition,
            archived=(archived_partition == "t"),
        )

        count = endpoint_content["count"]

        yield Output(
            value=(
                endpoint_content["data"],
                get_avro_record_schema(
                    name=asset_name, fields=ASSET_FIELDS[asset_name]
                ),
            ),
            metadata={"records": count},
        )

    return _asset
