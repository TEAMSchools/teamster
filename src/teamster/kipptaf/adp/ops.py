from dagster import AssetKey, In, OpExecutionContext, op
from dagster_gcp import BigQueryResource
from google.cloud import bigquery
from pandas import DataFrame

from teamster.core.adp.resources import AdpWorkforceNowResource

from .. import CODE_LOCATION


def get_event_payload(associate_oid, item_id, string_value):
    payload = {
        "data": {
            "eventContext": {"worker": {"associateOID": associate_oid}},
            "transform": {"worker": {}},
        }
    }

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


worker_endpoint = "/events/hr/v1/worker"


@op(
    ins={
        "foo": In(
            asset_key=AssetKey(
                [CODE_LOCATION, "extracts", "rpt_adp_workforce_now__worker_update"]
            )
        )
    }
)
def worker_fields_update_op(
    context: OpExecutionContext,
    db_bigquery: BigQueryResource,
    adp_wfn: AdpWorkforceNowResource,
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

    data = df.to_dict(orient="records")

    for i in data:
        # update work email if new
        if i["mail"] != record_match.get("work_email").get("emailUri"):
            context.log.info(
                f"{i['employee_number']}\twork_email"
                f"\t{record_match.get('work_email').get('emailUri')} => {i['mail']}"
            )

            work_email_data = get_event_payload(
                associate_oid=i["associate_oid"],
                item_id="Business",
                string_value=i["mail"],
            )

            adp_wfn.post(
                endpoint=worker_endpoint,
                subresource="business-communication.email",
                verb="change",
                payload={"events": [work_email_data]},
            )

        # update employee number if missing
        if not record_match.get("employee_number").get("stringValue"):
            context.log.info(
                f"{i['employee_number']}\temployee_number"
                f"\t{record_match.get('employee_number').get('stringValue')}"
                f" => {i['employee_number']}"
            )

            emp_num_data = get_event_payload(
                associate_oid=i["associate_oid"],
                item_id=record_match.get("employee_number").get("itemID"),
                string_value=i["employee_number"],
            )

            adp_wfn.post(
                endpoint=worker_endpoint,
                subresource="custom-field.string",
                verb="change",
                payload={"events": [emp_num_data]},
            )

        # update wfm badge number, if missing
        if not record_match.get("wfm_badge_number").get("stringValue"):
            context.log.info(
                f"{i['employee_number']}\twfm_badge_number"
                f"\t{record_match.get('wfm_badge_number').get('stringValue')}"
                f" => {i['employee_number']}"
            )

            wfm_badge_data = get_event_payload(
                associate_oid=i["associate_oid"],
                item_id=record_match.get("wfm_badge_number").get("itemID"),
                string_value=i["employee_number"],
            )

            adp_wfn.post(
                endpoint=worker_endpoint,
                subresource="custom-field.string",
                verb="change",
                payload={"events": [wfm_badge_data]},
            )

        # update wfm trigger if not null
        if i["wfm_trigger"]:
            context.log.info(
                f"{i['employee_number']}\twfm_trigger"
                f"\t{record_match.get('wfm_trigger').get('stringValue')}"
                f" => {i['wfm_trigger']}"
            )

            wfm_trigger_data = get_event_payload(
                associate_oid=i["associate_oid"],
                item_id=record_match.get("wfm_trigger").get("itemID"),
                string_value=i["wfm_trigger"],
            )

            adp_wfn.post(
                endpoint=worker_endpoint,
                subresource="custom-field.string",
                verb="change",
                payload={"events": [wfm_trigger_data]},
            )
