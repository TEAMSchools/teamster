from dagster import AssetKey, In, OpExecutionContext, op
from dagster_gcp import BigQueryResource
from google.cloud import bigquery
from pandas import DataFrame

from teamster.core.adp.resources import AdpWorkforceNowResource

from .. import CODE_LOCATION


def get_base_payload(associate_oid):
    return {
        "data": {
            "eventContext": {"worker": {"associateOID": associate_oid}},
            "transform": {"worker": {}},
        }
    }


def get_event_payload(associate_oid, item_id, string_value):
    payload = get_base_payload(associate_oid)

    if item_id == "Business":
        payload["data"]["transform"]["worker"]["businessCommunication"] = {
            "email": {"emailUri": string_value}
        }
    else:
        payload["data"]["eventContext"]["worker"]["customFieldGroup"] = {
            "stringField": {"itemID": item_id}
        }
        payload["data"]["transform"]["worker"]["customFieldGroup"] = {
            "stringField": {"stringValue": string_value}
        }

    return payload


@op(
    ins={
        "source_view": In(
            asset_key=AssetKey(
                [CODE_LOCATION, "extracts", "rpt_adp_workforce_now__worker_update"]
            )
        )
    }
)
def adp_wfn_worker_fields_update_op(
    context: OpExecutionContext,
    db_bigquery: BigQueryResource,
    adp_wfn: AdpWorkforceNowResource,
    source_view,
):
    # query extract view
    dataset_ref = bigquery.DatasetReference(
        project=db_bigquery.project, dataset_id=f"{CODE_LOCATION}_extracts"
    )

    with db_bigquery.get_client() as bq:
        table = bq.get_table(
            dataset_ref.table(table_id="rpt_adp_workforce_now__worker_update")
        )

        rows = bq.list_rows(table=table)

    df: DataFrame = rows.to_dataframe()

    worker_data = df.to_dict(orient="records")

    for worker in worker_data:
        associate_oid = worker["associate_oid"]
        employee_number = worker["employee_number"]

        # update work email if new
        mail = worker["mail"]
        mail_adp = worker["communication_business_email"]

        if mail != mail_adp or mail_adp is None:
            context.log.info(f"{employee_number}\twork_email\t{mail_adp} => {mail}")
            adp_wfn.post(
                endpoint="/events/hr/v1/worker",
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

        # update employee number if missing
        employee_number_adp = worker["custom_employee_number"]

        if employee_number_adp is None:
            context.log.info(
                f"{employee_number}\tcustom_employee_number\t{employee_number_adp}"
                f" => {employee_number}"
            )

            adp_wfn.post(
                endpoint="/events/hr/v1/worker",
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

        # update wfm badge number, if missing
        wfmgr_badge_number_adp = worker["custom_wfmgr_badge_number"]

        if wfmgr_badge_number_adp is None:
            context.log.info(
                f"{employee_number}\twfmgr_badge_number\t{wfmgr_badge_number_adp}"
                f" => {employee_number}"
            )

            adp_wfn.post(
                endpoint="/events/hr/v1/worker",
                subresource="custom-field.string",
                verb="change",
                payload={
                    "events": [
                        get_event_payload(
                            associate_oid=associate_oid,
                            item_id="9200137663381_1",
                            string_value=employee_number,
                        )
                    ]
                },
            )

        # update wfm trigger if not null
        wfmgr_trigger = worker["wfmgr_trigger"]
        wfmgr_trigger_adp = worker["custom_wfmgr_trigger"]

        if wfmgr_trigger is not None:
            context.log.info(
                f"{employee_number}\twfm_trigger\t{wfmgr_trigger_adp}"
                f" => {wfmgr_trigger}"
            )

            adp_wfn.post(
                endpoint="/events/hr/v1/worker",
                subresource="custom-field.string",
                verb="change",
                payload={
                    "events": [
                        get_event_payload(
                            associate_oid=associate_oid,
                            item_id="9200039822128_1",
                            string_value=wfmgr_trigger,
                        )
                    ]
                },
            )


__all__ = [
    adp_wfn_worker_fields_update_op,
]
