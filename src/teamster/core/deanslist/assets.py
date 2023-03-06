from collections import namedtuple

import pendulum
from dagster import (
    AssetsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    asset,
)

from teamster.core.deanslist.schema import get_avro_schema
from teamster.core.resources.deanslist import DeansList
from teamster.core.utils.classes import FiscalYear


def build_deanslist_endpoint_asset(
    asset_name,
    code_location,
    api_version,
    partitions_def: MultiPartitionsDefinition = None,
    inception_date=None,
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
        if hasattr(context.partition_key, "keys_by_dimension"):
            school_partition = context.partition_key.keys_by_dimension["school"]
            date_partition = pendulum.parser.parse(
                context.partition_key.keys_by_dimension["date"]
            )

            if (
                context.instance.get_latest_materialization_event(
                    context.selected_asset_keys[0]
                )
                is None
            ):
                FY = namedtuple("FiscalYear", ["start", "end"])
                fiscal_year = FY(start=inception_date, end=date_partition)
                modified_date = inception_date
            else:
                fiscal_year = FiscalYear(datetime=date_partition, start_month=7)
                modified_date = date_partition

            for k, v in params.items():
                if isinstance(v, str):
                    params[k] = v.format(
                        start_date=fiscal_year.start.to_date_string(),
                        end_date=fiscal_year.end.to_date_string(),
                        modified_date=modified_date.to_date_string(),
                    )
        else:
            school_partition = context.partition_key

        dl: DeansList = context.resources.deanslist

        row_count, data = dl.get_endpoint(
            api_version=api_version,
            endpoint=asset_name,
            school_id=int(school_partition),
            **params,
        )

        if row_count > 0:
            yield Output(
                value=(data, get_avro_schema(name=asset_name, version=api_version)),
                metadata={"records": row_count},
            )

    return _asset
