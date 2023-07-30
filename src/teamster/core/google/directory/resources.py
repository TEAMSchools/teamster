import google.auth
from dagster import ConfigurableResource, InitResourceContext
from googleapiclient import discovery
from pydantic import PrivateAttr


class GoogleDirectoryResource(ConfigurableResource):
    customer_id: str
    service_account_file_path: str = None
    delegated_account: str = None
    version: str = "v1"
    scopes: list = ["https://www.googleapis.com/auth/admin.directory.user"]
    max_results: int = 500

    _service: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        if self.service_account_file_path is not None:
            credentials, project_id = google.auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )

            credentials = credentials.with_subject(self.delegated_account)
        else:
            credentials, project_id = google.auth.default(scopes=self.scopes)

        self._service = discovery.build(
            serviceName="admin",
            version=f"directory_{self.version}",
            credentials=credentials,
        )

    def list_users(self, **kwargs):
        customer = kwargs.get("customer", self.customer_id)

        users = []
        next_page_token = None
        while True:
            data = (
                self._service.users()
                .list(
                    customer=customer,
                    pageToken=next_page_token,
                    maxResults=self.max_results,
                    **kwargs,
                )
                .execute()
            )

            next_page_token = data.get("nextPageToken")
            users.extend(data["users"])

            self.get_resource_context().log.debug(f"Retrieved {len(users)} users")

            if next_page_token is None:
                break

        return users
