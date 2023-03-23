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

from teamster.core.deanslist.schema import ENDPOINT_FIELDS, get_avro_record_schema
from teamster.core.resources.deanslist import DeansList
from teamster.core.utils.classes import FiscalYear


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

        row_count, data = dl.get_endpoint(
            api_version=api_version,
            endpoint=asset_name,
            school_id=int(context.partition_key),
            **params,
        )

        if row_count > 0:
            yield Output(
                value=(
                    data,
                    get_avro_record_schema(
                        name=asset_name,
                        fields=ENDPOINT_FIELDS[asset_name],
                        version=api_version,
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

        # set fiscal year start and end
        if (
            school_materialization_count == 0
            or school_materialization_count == context.retry_number
        ):
            start_fy = FiscalYear(datetime=inception_date, start_month=7)

            if set(["StartDate", "EndDate"]).issubset(params.keys()):
                stop_fy = FiscalYear(datetime=date_partition, start_month=7)
            elif set(["sdt", "edt"]).issubset(params.keys()):
                stop_fy = FiscalYear(datetime=date_partition, start_month=7)
            else:
                stop_fy = FiscalYear(datetime=inception_date, start_month=7)

            modified_date = start_fy.start
        else:
            start_fy = FiscalYear(datetime=date_partition, start_month=7)
            stop_fy = FiscalYear(datetime=date_partition, start_month=7)
            modified_date = date_partition

        dl: DeansList = context.resources.deanslist

        total_row_count = 0
        all_data = []
        for fy in range(start_fy.fiscal_year, (stop_fy.fiscal_year + 1)):
            fiscal_year = FiscalYear(
                datetime=pendulum.datetime(year=fy, month=6, day=30), start_month=7
            )

            composed_params = copy.deepcopy(params)
            for k, v in composed_params.items():
                if isinstance(v, str):
                    composed_params[k] = v.format(
                        start_date=fiscal_year.start.to_date_string(),
                        end_date=fiscal_year.end.to_date_string(),
                        modified_date=modified_date.to_date_string(),
                    )

            row_count, data = dl.get_endpoint(
                api_version=api_version,
                endpoint=asset_name,
                school_id=int(school_partition),
                **composed_params,
            )

            if row_count > 0:
                total_row_count += row_count
                all_data.extend(data)

                del data
                gc.collect()

        yield Output(
            value=(
                all_data,
                get_avro_record_schema(
                    name=asset_name,
                    fields=ENDPOINT_FIELDS[asset_name],
                    version=api_version,
                ),
            ),
            metadata={"records": total_row_count},
        )

    return _asset
