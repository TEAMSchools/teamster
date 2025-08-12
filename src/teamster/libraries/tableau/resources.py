from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from tableauserverclient import Pager, PersonalAccessTokenAuth, RequestOptions, Server
from tableauserverclient.server.pager import CallableEndpoint, Endpoint


class TableauServerResource(ConfigurableResource):
    server_address: str
    token_name: str
    personal_access_token: str
    site_id: str

    _server: Server = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._server = Server(
            server_address=self.server_address, use_server_version=True
        )

        self._server.auth.sign_in(
            PersonalAccessTokenAuth(
                token_name=self.token_name,
                personal_access_token=self.personal_access_token,
                site_id=self.site_id,
            )
        )

    def get_all(self, endpoint: CallableEndpoint | Endpoint, pagesize: int = 100):
        return list(
            Pager(endpoint=endpoint, request_opts=RequestOptions(pagesize=pagesize))
        )
