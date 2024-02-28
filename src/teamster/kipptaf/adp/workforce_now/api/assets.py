from dagster import AssetExecutionContext, DailyPartitionsDefinition, Output, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)

from .... import CODE_LOCATION
from .resources import AdpWorkforceNowResource
from .schema import WORKER_SCHEMA

asset_key = [CODE_LOCATION, "adp", "workforce_now", "workers"]


@asset(
    key=asset_key,
    io_manager_key="io_manager_gcs_avro",
    group_name="adp_workforce_now",
    compute_kind="adp",
    check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    partitions_def=DailyPartitionsDefinition(
        start_date="01/01/2021", fmt="%m/%d/%Y", end_offset=1
    ),
)
def workers(context: AssetExecutionContext, adp_wfn: AdpWorkforceNowResource):
    records = adp_wfn.get_records(
        endpoint="hr/v2/workers", params={"asOfDate": context.partition_key}
    )

    yield Output(
        value=(records, WORKER_SCHEMA), metadata={"record_count": len(records)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=records, schema=WORKER_SCHEMA
    )


_all = [
    workers,
]
