from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from zenpy import Zenpy


class ZendeskResource(ConfigurableResource):
    subdomain: str
    email: str
    token: str

    _client: Zenpy = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client = Zenpy(
            subdomain=self.subdomain, email=self.email, token=self.token
        )
