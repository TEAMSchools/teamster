from collections import namedtuple

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

            context.log.debug(context.partition_time_window.start)
            context.log.debug(partitions_def.start)
            if context.partition_time_window.start == partitions_def.start:
                FY = namedtuple("FiscalYear", ["start", "end"])
                fiscal_year = FY(start=pendulum.date(2002, 7, 1), end=partition_key)
                modified_date = pendulum.date(2002, 7, 1)
            else:
                fiscal_year = FiscalYear(datetime=partition_key, start_month=7)
                modified_date = partition_key

            for k, v in params.items():
                if isinstance(v, str):
                    params[k] = v.format(
                        start_date=fiscal_year.start.to_date_string(),
                        end_date=fiscal_year.end.to_date_string(),
                        modified_date=modified_date.to_date_string(),
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
                value=(all_data, get_avro_schema(name=asset_name, version=api_version)),
                metadata={"records": total_row_count},
            )

    return _asset
