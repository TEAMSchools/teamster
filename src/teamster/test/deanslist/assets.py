# import pendulum
from dagster import OpExecutionContext, Output, asset

from teamster.core.resources.deanslist import DeansList

# from teamster.core.utils.classes import FiscalYear


@asset(
    name="users",
    key_prefix=["test", "deanslist"],
    required_resource_keys={"deanslist"},
    op_tags={},
    # partitions_def=...,
    output_required=False,
)
def users(context: OpExecutionContext):
    # partition_key = pendulum.parser.parse(context.partition_key)
    # fiscal_year = FiscalYear(datetime=partition_key, start_month=7)

    dl: DeansList = context.resources.deanslist
    total_row_count, all_data = dl.get_endpoint(
        # TODO: factory-ize this by endpoint/school_id
        endpoint="users",
        school_id=120,
        IncludeInactive="Y",
    )

    context.log.debug(all_data[0])

    if total_row_count is not None:
        return Output(value=all_data, metadata={"row_count": total_row_count})
