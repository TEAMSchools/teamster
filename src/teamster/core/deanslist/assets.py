# import pendulum
from dagster import (
    AssetsDefinition,
    OpExecutionContext,
    Output,
    TimeWindowPartitionsDefinition,
    asset,
)

from teamster.core.resources.deanslist import DeansList

# from teamster.core.utils.classes import FiscalYear


def build_deanslist_endpoint_asset(
    asset_name,
    code_location,
    partitions_def: TimeWindowPartitionsDefinition = None,
    op_tags={},
    **kwargs,
) -> AssetsDefinition:
    @asset(
        name=asset_name,
        key_prefix=[code_location, "deanslist"],
        partitions_def=partitions_def,
        op_tags=op_tags,
        required_resource_keys={"deanslist"},
        io_manager_key="gcs_avro_io",
        output_required=False,
    )
    def _asset(context: OpExecutionContext):
        # partition_key = pendulum.parser.parse(context.partition_key)
        # fiscal_year = FiscalYear(datetime=partition_key, start_month=7)

        dl: DeansList = context.resources.deanslist
        total_row_count, all_data = dl.get_endpoint(
            # TODO: factory-ize this by endpoint/school_id
            endpoint=asset_name,
            school_id=120,
            **kwargs,
        )

        if total_row_count is not None:
            return Output(value=all_data, metadata={"records": total_row_count})

    return _asset
