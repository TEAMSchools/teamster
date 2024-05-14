import json
import pathlib

from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.kipptaf.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)

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


@asset(partitions_def=StaticPartitionsDefinition(PUBLISHED_ACTION_IDS))
def submission_records(
    context: AssetExecutionContext, ps_enrollment: PowerSchoolEnrollmentResource
):
    data = ps_enrollment.get_all_records(
        endpoint=f"publishedactions/{context.partition_key}/submissionrecords"
    )

    fp = pathlib.Path("env/psenr/submission_records.json")
    fp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=data, fp=fp.open("w"))

    yield Output(value=data, metadata={"records": len(data)})
