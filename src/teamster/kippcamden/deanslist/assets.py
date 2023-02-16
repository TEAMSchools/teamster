import pendulum
from dagster import OpExecutionContext, asset

from teamster.core.resources.deanslist import DeansList
from teamster.core.utils.classes import FiscalYear


@asset(required_resource_keys={"deanslist"}, key_prefix=[], partitions_def=...)
def behavior(context: OpExecutionContext):
    partition_key = pendulum.parser.parse(context.partition_key)
    fiscal_year = FiscalYear(datetime=partition_key, start_month=7)

    dl: DeansList = context.resources.deanslist
    response = dl.get_endpoint(
        # TODO: factory-ize this by endpoint/school_id
        endpoint="behavior",
        school_id=120,
        StartDate=fiscal_year.start.to_date_string(),
        EndDate=fiscal_year.end.to_date_string(),
        UpdatedSince=partition_key.to_date_string(),
        IncludeDeleted="Y",
    )

    row_count = response.get("rowcount")
    deleted_row_count = response.get("deleted_rowcount", 0)
    total_row_count = row_count + deleted_row_count

    data = response.get("data")
    deleted_data = response.get("deleted_data")
    all_data = data + deleted_data
