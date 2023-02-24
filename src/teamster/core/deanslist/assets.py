import pendulum
from dagster import (
    AssetsDefinition,
    OpExecutionContext,
    Output,
    TimeWindowPartitionsDefinition,
    asset,
)

from teamster.core.deanslist.schema import get_avro_schema
from teamster.core.resources.deanslist import DeansList
from teamster.core.utils.classes import FiscalYear


def build_deanslist_endpoint_asset(
    asset_name,
    code_location,
    api_version,
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
        if partitions_def is not None:
            partition_key = pendulum.parser.parse(context.partition_key)

            fiscal_year = FiscalYear(datetime=partition_key, start_month=7)

            for k, v in params.items():
                if isinstance(v, str):
                    params[k] = v.format(
                        fiscal_year_start=fiscal_year.start.to_date_string(),
                        fiscal_year_end=fiscal_year.end.to_date_string(),
                        partition_key=partition_key.to_date_string(),
                    )

        dl: DeansList = context.resources.deanslist

        total_row_count = 0
        all_data = []
        for school_id in school_ids:
            row_count, data = dl.get_endpoint(
                api_version=api_version,
                endpoint=asset_name,
                school_id=school_id,
                **params,
            )

            total_row_count += row_count
            all_data.extend(data)

        if total_row_count is not None:
            yield Output(
                value=(all_data, get_avro_schema(asset_name)),
                metadata={"records": total_row_count},
            )

    return _asset
