import requests
from dagster import ConfigurableResource, InitResourceContext
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import exceptions
from requests_oauthlib import OAuth2Session
from tenacity import retry, stop_after_attempt, wait_exponential


class AdpWorkforceNowResource(ConfigurableResource):
    client_id: str
    client_secret: str
    cert_filepath: str
    key_filepath: str

    _service_root: str = PrivateAttr(default="https://api.adp.com")
    _session: OAuth2Session = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        # instantiate client
        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        client = BackendApplicationClient(client_id=self.client_id)
        self._session = OAuth2Session(client=client)
        self._session.cert = (self.cert_filepath, self.key_filepath)

        # authorize client
        token_dict = self._session.fetch_token(
            token_url="https://accounts.adp.com/auth/oauth/v2/token", auth=auth
        )
        access_token = token_dict.get("access_token")
        self._session.headers["Authorization"] = f"Bearer {access_token}"

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _request(self, method, url, **kwargs):
        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            self.get_resource_context().log.error(e, response.text)

            raise exceptions.HTTPError() from e

    def post(self, endpoint, subresource, verb, payload):
        url = f"{self._service_root}{endpoint}.{subresource}.{verb}"

        return self._request(method="POST", url=url, json=payload)
