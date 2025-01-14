import google.auth
from dagster import ConfigurableResource, InitResourceContext
from googleapiclient import discovery
from pydantic import PrivateAttr
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


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

    def get_form(self, form_id: str):
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.get(formId=form_id).execute()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter())
    def _execute_list_responses(self, **kwargs) -> dict:
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.responses().list(**kwargs).execute()

    def list_responses(self, form_id: str, **kwargs):
        page_token = None
        reponses = []

        while True:
            data = self._execute_list_responses(
                formId=form_id, pageToken=page_token, **kwargs
            )

            reponses.extend(data.get("responses", []))
            page_token = data.get("nextPageToken")

            if page_token is None:
                break
            # pageSize=1 only used to check for new responses in sensor
            elif kwargs.get("pageSize") == 1:
                break

        return reponses
