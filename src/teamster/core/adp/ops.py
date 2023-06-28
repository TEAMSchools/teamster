from dagster import OpExecutionContext, op
from dagster_gcp import BigQueryResource

from teamster.core.adp.resources import AdpWorkforceNowResource


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


@op()
def _op(
    context: OpExecutionContext,
    db_bigquery: BigQueryResource,
    adp_wfn: AdpWorkforceNowResource,
):
    # query extract view
    worker_extract = []

    for i in worker_extract:
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
