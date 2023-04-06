import copy
import gc

import pendulum
from dagster import (
    AssetsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from teamster.core.deanslist.resources import DeansList
from teamster.core.deanslist.schema import ENDPOINT_FIELDS
from teamster.core.utils.classes import FiscalYear
from teamster.core.utils.functions import get_avro_record_schema


def build_deanslist_static_partition_asset(
    asset_name,
    code_location,
    api_version,
    partitions_def: StaticPartitionsDefinition = None,
    op_tags={},
    params={},
) -> AssetsDefinition:
    @asset(
        name=asset_name.replace("-", "_"),
        key_prefix=[code_location, "deanslist"],
        partitions_def=partitions_def,
        op_tags=op_tags,
        required_resource_keys={"deanslist"},
        io_manager_key="gcs_avro_io",
        output_required=False,
    )
    def _asset(context: OpExecutionContext):
        dl: DeansList = context.resources.deanslist

        endpoint_content = dl.get_endpoint(
            api_version=api_version,
            endpoint=asset_name,
            school_id=int(context.partition_key),
            **params,
        )

        row_count = endpoint_content["row_count"]

        if row_count > 0:
            yield Output(
                value=(
                    endpoint_content["data"],
                    get_avro_record_schema(
                        name=asset_name, fields=ENDPOINT_FIELDS[asset_name][api_version]
                    ),
                ),
                metadata={"records": row_count},
            )

    return _asset


def build_deanslist_multi_partition_asset(
    asset_name,
    code_location,
    api_version,
    partitions_def: MultiPartitionsDefinition,
    inception_date=None,
    op_tags={},
    params={},
) -> AssetsDefinition:
    @asset(
        name=asset_name.replace("-", "_"),
        key_prefix=[code_location, "deanslist"],
        partitions_def=partitions_def,
        op_tags=op_tags,
        required_resource_keys={"deanslist"},
        io_manager_key="gcs_avro_io",
        output_required=False,
    )
    def _asset(context: OpExecutionContext):
        asset_key = context.asset_key_for_output()
        school_partition = context.partition_key.keys_by_dimension["school"]
        date_partition = pendulum.from_format(
            string=context.partition_key.keys_by_dimension["date"], fmt="YYYY-MM-DD"
        ).subtract(days=1)

        # check if school paritition has ever been materialized
        school_materialization_count = 0
        asset_materialization_counts = (
            context.instance.get_materialization_count_by_partition([asset_key]).get(
                asset_key, {}
            )
        )
        for partition_key, count in asset_materialization_counts.items():
            if school_partition == partition_key.split("|")[-1]:
                school_materialization_count += count

        # determine if endpoint is within time-window
        if set(["StartDate", "EndDate"]).issubset(params.keys()) or set(
            ["sdt", "edt"]
        ).issubset(params.keys()):
            is_time_bound = True
        else:
            is_time_bound = False

        # determine start and end dates
        partition_fy = FiscalYear(datetime=date_partition, start_month=7)
        inception_fy = FiscalYear(datetime=inception_date, start_month=7)

        if (
            school_materialization_count == 0
            or school_materialization_count == context.retry_number
        ):
            start_date = inception_fy.start
            if is_time_bound:
                end_date = partition_fy.end
            else:
                end_date = inception_fy.end

            partition_modified_date = None
        else:
            start_date = partition_fy.start
            end_date = partition_fy.end
            partition_modified_date = date_partition

        dl: DeansList = context.resources.deanslist

        multiyear_period = end_date - start_date
        total_row_count = 0
        all_data = []

        for year_start in multiyear_period.range(unit="years"):
            fiscal_year = FiscalYear(datetime=year_start, start_month=7)

            fy_period = fiscal_year.end - fiscal_year.start

            for month in fy_period.range(unit="months"):
                modified_date = partition_modified_date or fiscal_year.start
                composed_params = copy.deepcopy(params)

                for k, v in composed_params.items():
                    if isinstance(v, str):
                        composed_params[k] = v.format(
                            start_date=month.start_of("month").to_date_string(),
                            end_date=month.end_of("month").to_date_string(),
                        )

                endpoint_content = dl.get_endpoint(
                    api_version=api_version,
                    endpoint=asset_name,
                    school_id=int(school_partition),
                    UpdatedSince=modified_date.to_date_string(),
                    **composed_params,
                )

                row_count = endpoint_content["row_count"]

                if row_count > 0:
                    total_row_count += row_count
                    all_data.extend(endpoint_content["data"])

                    del data
                    gc.collect()

                # break loop for endpoints w/o start/end dates
                if not is_time_bound:
                    break

        yield Output(
            value=(
                all_data,
                get_avro_record_schema(
                    name=asset_name, fields=ENDPOINT_FIELDS[asset_name][api_version]
                ),
            ),
            metadata={"records": total_row_count},
        )

    return _asset
