from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from tableauserverclient.models.tableau_auth import PersonalAccessTokenAuth
from tableauserverclient.server.server import Server
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


class TableauServerResource(ConfigurableResource):
    server_address: str
    token_name: str
    personal_access_token: str
    site_id: str

    _server: Server = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._server = Server(server_address=self.server_address)
        self._resolve_server_version()

        self._server.auth.sign_in(
            PersonalAccessTokenAuth(
                token_name=self.token_name,
                personal_access_token=self.personal_access_token,
                site_id=self.site_id,
            )
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def _resolve_server_version(self) -> None:
        initial_version = self._server.version
        self._server.use_server_version()

        if self._server.version == initial_version:
            msg = f"Tableau API version discovery failed — version unchanged at {initial_version!r}"
            raise ConnectionError(msg)
