import google.auth
from dagster import ConfigurableResource, InitResourceContext
from googleapiclient import discovery
from pydantic import PrivateAttr


class GoogleFormsResource(ConfigurableResource):
    service_account_file_path: str | None = None
    version: str = "v1"
    scopes: list = [
        "https://www.googleapis.com/auth/forms.body.readonly",
        "https://www.googleapis.com/auth/forms.responses.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ]

    _service: discovery.Resource = PrivateAttr()
    _drive: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        if self.service_account_file_path is not None:
            credentials, project_id = google.auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )
        else:
            credentials, project_id = google.auth.default(scopes=self.scopes)

        self._service = discovery.build(
            serviceName="forms", version=self.version, credentials=credentials
        ).forms()

        self._drive = discovery.build(
            serviceName="drive", version="v3", credentials=credentials
        ).files()

    def get_form(self, form_id):
        return self._service.get(formId=form_id).execute()  # type: ignore

    def list_responses(self, form_id, **kwargs):
        return self._service.responses().list(formId=form_id, **kwargs).execute()  # type: ignore

    def list_forms(self):
        return self._drive.list(  # type: ignore
            q="mimeType='application/vnd.google-apps.form'"
        ).execute()
