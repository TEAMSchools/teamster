from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    DailyPartitionsDefinition,
    Output,
    asset,
)
from dagster_gcp import BigQueryResource

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.schema import WORKER_SCHEMA
from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource
from teamster.libraries.adp.workforce_now.api.utils import get_event_payload

key_prefix = [CODE_LOCATION, "adp", "workforce_now"]
asset_kwargs = {
    "group_name": "adp_workforce_now",
    "kinds": {"python"},
    "pool": "adp_wfn_api",
}


@asset(
    key=[*key_prefix, "workers"],
    io_manager_key="io_manager_gcs_avro",
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "workers"])],
    partitions_def=DailyPartitionsDefinition(
        start_date="01/01/2021",
        fmt="%m/%d/%Y",
        timezone=str(LOCAL_TIMEZONE),
        end_offset=14,
    ),
    **asset_kwargs,
)
def adp_workforce_now_workers(
    context: AssetExecutionContext, adp_wfn: AdpWorkforceNowResource
):
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


@asset(
    key=[*key_prefix, "workers_sync"],
    check_specs=[
        AssetCheckSpec(name="zero_api_errors", asset=[*key_prefix, "workers_sync"])
    ],
    **asset_kwargs,
)
def adp_workforce_now_workers_update(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    adp_wfn: AdpWorkforceNowResource,
):
    query = "select * from kipptaf_extracts.rpt_adp_workforce_now__worker_update"
    errors = []

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")
    worker_data = arrow.to_pylist()

    for worker in worker_data:
        associate_oid = worker["associate_oid"]
        employee_number = worker["employee_number"]

        # update work email if missing or different
        mail = worker["mail"]
        mail_adp = worker["adp__work_email"]

        if mail != mail_adp or mail_adp is None:
            context.log.info(f"{employee_number}\twork_email\t{mail_adp} => {mail}")
            try:
                adp_wfn.post(
                    endpoint="events/hr/v1/worker",
                    subresource="business-communication.email",
                    verb="change",
                    payload={
                        "events": [
                            get_event_payload(
                                associate_oid=associate_oid,
                                item_id="Business",
                                string_value=mail,
                            )
                        ]
                    },
                )
            except Exception as e:
                context.log.error(msg=str(e))
                errors.append(str(e))
                pass

        # update employee number if missing
        employee_number_adp = worker["adp__custom_field__employee_number"]

        if employee_number_adp is None:
            context.log.info(
                f"{employee_number}\temployee_number\t{employee_number_adp}"
                f" => {employee_number}"
            )

            try:
                adp_wfn.post(
                    endpoint="events/hr/v1/worker",
                    subresource="custom-field.string",
                    verb="change",
                    payload={
                        "events": [
                            get_event_payload(
                                associate_oid=associate_oid,
                                item_id="9200112834881_1",
                                string_value=employee_number,
                            )
                        ]
                    },
                )
            except Exception as e:
                context.log.error(msg=str(e))
                errors.append(str(e))
                pass

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": str(errors)},
        severity=AssetCheckSeverity.WARN,
    )


assets = [
    adp_workforce_now_workers,
    adp_workforce_now_workers_update,
]
