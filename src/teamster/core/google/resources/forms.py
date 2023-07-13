import google.auth
from dagster import ConfigurableResource
from dagster._core.execution.context.init import InitResourceContext
from googleapiclient import discovery
from pydantic import PrivateAttr


class GoogleFormsResource(ConfigurableResource):
    version: str = "v1"
    scopes: list = [
        "https://www.googleapis.com/auth/forms.body.readonly",
        "https://www.googleapis.com/auth/forms.responses.readonly",
    ]

    _service: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        credentials, _ = google.auth.default(scopes=self.scopes)

        self._service = discovery.build(
            serviceName="forms",
            version=self.version,
            credentials=credentials,
            discoveryServiceUrl="https://forms.googleapis.com/$discovery/rest",
        ).forms()

    def get_form(self, form_id):
        return self._service.get(formId=form_id).execute()

    def list_responses(self, form_id, **kwargs):
        return self._service.responses().list(formId=form_id, **kwargs).execute()
