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
    school_ids,
    partitions_def: TimeWindowPartitionsDefinition = None,
    op_tags={},
    params={},
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

        total_row_count = 0
        all_data = []
        for school_id in school_ids:
            row_count, data = dl.get_endpoint(
                endpoint=asset_name, school_id=school_id, **params
            )

            total_row_count += row_count
            all_data.extend(data)

        if total_row_count is not None:
            return Output(value=all_data, metadata={"records": total_row_count})

    return _asset
