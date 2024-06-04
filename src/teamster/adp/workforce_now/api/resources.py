from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session
from tenacity import retry, stop_after_attempt, wait_exponential


class AdpWorkforceNowResource(ConfigurableResource):
    client_id: str
    client_secret: str
    cert_filepath: str
    key_filepath: str

    _service_root: str = PrivateAttr(default="https://api.adp.com")
    _session: OAuth2Session = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

        # instantiate client
        self._session = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id)
        )
        self._session.cert = (self.cert_filepath, self.key_filepath)

        # authorize client
        # trunk-ignore(bandit/B106)
        token_dict = self._session.fetch_token(
            token_url="https://accounts.adp.com/auth/oauth/v2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

        access_token = token_dict.get("access_token")

        self._session.headers["Authorization"] = f"Bearer {access_token}"

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _request(self, method, url, **kwargs):
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise HTTPError() from e

    def post(self, endpoint, subresource, verb, payload):
        return self._request(
            method="POST",
            url=f"{self._service_root}/{endpoint}.{subresource}.{verb}",
            json=payload,
        )

    def get(self, endpoint, params: dict | None = None):
        if params is None:
            params = {}

        return self._request(
            method="GET", url=f"{self._service_root}/{endpoint}", params=params
        )

    def get_records(self, endpoint, params: dict | None = None) -> list[dict]:
        page_size = 100
        all_records = []

        if params is None:
            params = {}

        endpoint_name = endpoint.split("/")[-1]

        params.update({"$top": page_size, "$skip": 0})

        while True:
            self._log.debug(params)
            response = self.get(endpoint=endpoint, params=params)

            if response.status_code == 204:
                break

            response_json = response.json()[endpoint_name]

            all_records.extend(response_json)

            params.update({"$skip": params["$skip"] + page_size})

        return all_records
