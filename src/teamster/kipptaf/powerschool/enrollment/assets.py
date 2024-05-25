from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.powerschool.enrollment.schema import SUBMISSION_RECORD_SCHEMA
from teamster.powerschool.enrollment.resources import PowerSchoolEnrollmentResource

PUBLISHED_ACTION_IDS = [
    "1006",
    "10723",
    "12730",
    "1697",
    "17444",
    "22584",
    "2330",
    "25218",
    "27206",
    "31765",
    "3195",
    "33499",
    "3478",
    "35429",
    "39362",
    "4436",
    "4825",
    "504",
    "6952",
    "8876",
]


@asset(
    key=[CODE_LOCATION, "powerschool", "enrollment", "submission_records"],
    io_manager_key="io_manager_gcs_avro",
    group_name="powerschool",
    partitions_def=StaticPartitionsDefinition(PUBLISHED_ACTION_IDS),
    check_specs=[
        get_avro_schema_valid_check_spec(
            [CODE_LOCATION, "powerschool", "enrollment", "submission_records"]
        )
    ],
)
def submission_records(
    context: AssetExecutionContext, ps_enrollment: PowerSchoolEnrollmentResource
):
    data = ps_enrollment.get_all_records(
        endpoint=f"publishedactions/{context.partition_key}/submissionrecords"
    )

    yield Output(
        value=(data, SUBMISSION_RECORD_SCHEMA), metadata={"records": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SUBMISSION_RECORD_SCHEMA
    )


assets = [
    submission_records,
]
