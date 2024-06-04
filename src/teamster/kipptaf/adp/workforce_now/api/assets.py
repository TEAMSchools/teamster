from dagster import AssetExecutionContext, DailyPartitionsDefinition, Output, asset

from teamster.adp.workforce_now.api.resources import AdpWorkforceNowResource
from teamster.core.utils.functions import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.kipptaf.adp.workforce_now.api.schema import WORKER_SCHEMA

asset_key = [CODE_LOCATION, "adp", "workforce_now", "workers"]


@asset(
    key=asset_key,
    io_manager_key="io_manager_gcs_avro",
    group_name="adp_workforce_now",
    compute_kind="python",
    check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    partitions_def=DailyPartitionsDefinition(
        start_date="01/01/2021", fmt="%m/%d/%Y", timezone=LOCAL_TIMEZONE.name
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


assets = [
    workers,
]
