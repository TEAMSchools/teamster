from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout
from tableauserverclient.models.tableau_auth import PersonalAccessTokenAuth
from tableauserverclient.server.server import Server
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class TableauServerResource(ConfigurableResource):
    server_address: str
    token_name: str
    personal_access_token: str
    site_id: str
    api_version: str = "3.25"

    _server: Server = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._server = Server(server_address=self.server_address)
        self._server.version = self.api_version

        self._sign_in()

    @retry(
        retry=retry_if_exception_type((RequestsConnectionError, Timeout)),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=60),
        reraise=True,
    )
    def _sign_in(self) -> None:
        """Sign in to Tableau Server with the PAT, retrying transient faults.

        Regression for prod run 136d2259: the server dropped the TCP connection
        mid-TLS-handshake during sign-in, raising a
        ``requests.exceptions.ConnectionError``. Resource init has no other retry
        layer, so a single blip failed the step and the run. Only network faults
        (``ConnectionError``/``Timeout``) are retried — an ``HTTPError`` here
        means a deterministic auth failure (invalid or expired PAT) that must
        fail fast rather than burn retries.
        """
        self._server.auth.sign_in(
            PersonalAccessTokenAuth(
                token_name=self.token_name,
                personal_access_token=self.personal_access_token,
                site_id=self.site_id,
            )
        )
