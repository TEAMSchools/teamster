import requests
from dagster import ConfigurableResource, InitResourceContext
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Session, exceptions
from requests_oauthlib import OAuth2Session
from tenacity import retry, stop_after_attempt, wait_exponential


class AdpWorkforceManagerResource(ConfigurableResource):
    subdomain: str
    app_key: str
    client_id: str
    client_secret: str
    username: str
    password: str

    _client: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr()
    _refresh_token: str = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._base_url = f"https://{self.subdomain}.mykronos.com/api"

        self._client.headers["appkey"] = self.app_key

        self._authenticate(grant_type="password")

    def _authenticate(self, grant_type):
        self._client.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self._client.headers.pop(
            "Authorization", ""
        )  # remove existing auth for refresh

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": grant_type,
            "auth_chain": "OAuthLdapService",
        }

        if grant_type == "refresh_token":
            payload["refresh_token"] = self._refresh_token
        else:
            payload["username"] = self.username
            payload["password"] = self.password

        response = self._client.post(
            f"{self._base_url}/authentication/access_token", data=payload
        )

        response.raise_for_status()
        response_data = response.json()

        self._refresh_token = response_data["refresh_token"]
        self._client.headers["Content-Type"] = "application/json"
        self._client.headers["Authorization"] = (
            "Bearer " + response_data["access_token"]
        )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _request(self, method, url, **kwargs):
        try:
            response = self._client.request(method=method, url=url, **kwargs)

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            self.get_resource_context().log.error(e)

            if response.status_code == 401:
                self._authenticate(grant_type="refresh_token")
                self._request(method=method, url=url, **kwargs)
            else:
                raise exceptions.HTTPError(response.text) from e

    def _get_url(self, endpoint, *args):
        return f"{self._base_url}/{endpoint}" + ("/" + "/".join(args) if args else "")

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint=endpoint, *args)
        self.get_resource_context().log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def post(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint=endpoint, *args)
        self.get_resource_context().log.debug(f"POST: {url}")

        return self._request(method="POST", url=url, **kwargs)


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
            self.get_resource_context().log.error(e)

            raise exceptions.HTTPError(response.text) from e

    def get_record(self, endpoint, querystring={}, id=None, object_name=None):
        url = f"{self._service_root}{endpoint}"
        if id:
            url = f"{url}/{id}"

        r = self._session.get(url=url, params=querystring)

        if r.status_code == 204:
            return None

        if r.status_code == 200:
            data = r.json()
            object_name = object_name or endpoint.split("/")[-1]
            return data.get(object_name)
        else:
            r.raise_for_status()

    def get_all_records(self, endpoint, querystring={}, object_name=None):
        querystring["$skip"] = querystring.get("$skip", 0)
        all_data = []

        while True:
            data = self.get_record(
                endpoint=endpoint, querystring=querystring, object_name=object_name
            )

            if data is None:
                break
            else:
                all_data.extend(data)
                querystring["$skip"] += 50

        return all_data

    def post(self, endpoint, subresource, verb, payload):
        url = f"{self._service_root}{endpoint}.{subresource}.{verb}"

        return self._request(method="POST", url=url, json=payload)
