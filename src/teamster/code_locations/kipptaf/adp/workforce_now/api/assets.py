from dagster import AssetExecutionContext, DailyPartitionsDefinition, Output, asset

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.schema import WORKER_SCHEMA
from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)

asset_key = [CODE_LOCATION, "adp", "workforce_now", "workers"]


@asset(
    key=asset_key,
    io_manager_key="io_manager_gcs_avro",
    group_name="adp_workforce_now",
    compute_kind="python",
    check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    partitions_def=DailyPartitionsDefinition(
        start_date="01/01/2021",
        fmt="%m/%d/%Y",
        timezone=LOCAL_TIMEZONE.name,
        end_offset=14,
    ),
)
def workers(context: AssetExecutionContext, adp_wfn: AdpWorkforceNowResource):
    records = adp_wfn.get_records(
        endpoint="hr/v2/workers",
        params={
            "asOfDate": context.partition_key,
            "$select": ",".join(
                [
                    "workers/associateOID",
                    "workers/workerID",
                    "workers/workerDates",
                    "workers/workerStatus",
                    "workers/businessCommunication",
                    "workers/workAssignments",
                    "workers/customFieldGroup",
                    "workers/languageCode",
                    "workers/person/birthDate",
                    "workers/person/communication",
                    "workers/person/customFieldGroup",
                    "workers/person/disabledIndicator",
                    "workers/person/ethnicityCode",
                    "workers/person/genderCode",
                    "workers/person/genderSelfIdentityCode",
                    "workers/person/highestEducationLevelCode",
                    "workers/person/legalAddress",
                    "workers/person/legalName",
                    "workers/person/militaryClassificationCodes",
                    "workers/person/militaryStatusCode",
                    "workers/person/preferredName",
                    "workers/person/raceCode",
                ]
            ),
        },
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
