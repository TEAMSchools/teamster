import json

from dagster import build_resources

from teamster.core.google.resources.forms import GoogleFormsResource

FORM_ID = "1-YHFfRxZtEtXO7lMpTnINMWkpIbXzPh0p-56AZ5qBc4"


def test_resource():
    with build_resources(resources={"forms": GoogleFormsResource()}) as resources:
        forms: GoogleFormsResource = resources.forms

        form_data = forms.get_form(form_id=FORM_ID)
        # print(form_data)

        form_response_data = forms.list_responses(form_id=FORM_ID)
        # print(form_response_data)

    with open(file="env/form.json", mode="w") as f:
        json.dump(form_data, f)

    with open(file="env/form_responses.json", mode="w") as f:
        json.dump(form_response_data, f)
