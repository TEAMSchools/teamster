import json

from dagster import build_resources

from teamster.core.google.forms.resources import GoogleFormsResource

FORM_ID = "1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA"


def test_resource():
    with build_resources(
        resources={
            "forms": GoogleFormsResource(
                service_account_file_path="env/gcloud_service_account_json"
            )
        }
    ) as resources:
        forms: GoogleFormsResource = resources.forms

    form_data = forms.get_form(form_id=FORM_ID)
    # print(form_data)

    form_response_data = forms.list_responses(form_id=FORM_ID)
    # print(form_response_data)

    with open(file="env/form.json", mode="w") as f:
        json.dump(form_data, f)

    with open(file="env/responses.json", mode="w") as f:
        json.dump(form_response_data, f)
