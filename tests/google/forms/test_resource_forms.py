import json

from dagster import build_resources

from teamster.core.google.forms.resources import GoogleFormsResource


def _test_resource(form_id):
    with build_resources(
        resources={
            "forms": GoogleFormsResource(
                service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
            )
        }
    ) as resources:
        forms: GoogleFormsResource = resources.forms

    form_data = forms.get_form(form_id=form_id)
    # print(form_data)

    form_response_data = forms.list_responses(form_id=form_id)
    # print(form_response_data)

    json.dump(form_data, open(file=f"env/{form_id}_form.json", mode="w"))
    json.dump(form_response_data, open(file=f"env/{form_id}_responses.json", mode="w"))


def test_staff_info():
    _test_resource("1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA")


def test_support():
    _test_resource("1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI")


def test_manager():
    _test_resource("1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0")
