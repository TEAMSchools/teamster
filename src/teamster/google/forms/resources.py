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

    _resource: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        if self.service_account_file_path is not None:
            credentials, project_id = google.auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )
        else:
            credentials, project_id = google.auth.default(scopes=self.scopes)

        self._resource = discovery.build(
            serviceName="forms", version=self.version, credentials=credentials
        ).forms()

    def get_form(self, form_id):
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.get(formId=form_id).execute()

    def list_responses(self, form_id, **kwargs):
        page_token = None
        reponses = []

        while True:
            data: dict = (
                # trunk-ignore(pyright/reportAttributeAccessIssue)
                self._resource.responses()
                .list(formId=form_id, pageToken=page_token, **kwargs)
                .execute()
            )

            reponses.extend(data.get("responses", []))
            page_token = data.get("nextPageToken")

            if page_token is None:
                break

        return reponses
