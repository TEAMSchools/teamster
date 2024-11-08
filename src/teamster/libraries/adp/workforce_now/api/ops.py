from dagster import OpExecutionContext, op

from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource


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


@op
def adp_wfn_update_workers_op(
    context: OpExecutionContext, adp_wfn: AdpWorkforceNowResource, worker_data
):
    for worker in worker_data:
        associate_oid = worker["associate_oid"]
        employee_number = worker["employee_number"]

        # update work email if missing or different
        mail = worker["mail"]
        mail_adp = worker["adp__work_email"]

        if mail != mail_adp or mail_adp is None:
            context.log.info(f"{employee_number}\twork_email\t{mail_adp} => {mail}")
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

        # update employee number if missing
        employee_number_adp = worker["adp__custom_field__employee_number"]

        if employee_number_adp is None:
            context.log.info(
                f"{employee_number}\temployee_number\t{employee_number_adp}"
                f" => {employee_number}"
            )

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

        # update wfm badge number, if missing
        wfmgr_badge_number_adp = worker["adp__wf_mgr_badge_number"]

        if wfmgr_badge_number_adp is None:
            context.log.info(
                f"{employee_number}\twf_mgr_badge_number\t{wfmgr_badge_number_adp}"
                f" => {employee_number}"
            )

            adp_wfn.post(
                endpoint="events/hr/v1/worker",
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

        # update wfm trigger if missing or different
        wfmgr_trigger = worker["wf_mgr_trigger"]
        wfmgr_trigger_adp = worker["adp__wf_mgr_trigger"]

        if wfmgr_trigger != wfmgr_trigger_adp or wfmgr_trigger_adp is None:
            context.log.info(
                f"{employee_number}\twf_mgr_trigger\t{wfmgr_trigger_adp}"
                f" => {wfmgr_trigger}"
            )

            adp_wfn.post(
                endpoint="events/hr/v1/worker",
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
