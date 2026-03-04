def get_base_payload(associate_oid: str):
    return {
        "data": {
            "eventContext": {"worker": {"associateOID": associate_oid}},
            "transform": {"worker": {}},
        }
    }


def get_event_payload(associate_oid: str, item_id: str, string_value: str):
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
