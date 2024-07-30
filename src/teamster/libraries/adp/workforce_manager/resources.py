from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from requests import Response, Session, exceptions
from tenacity import retry, stop_after_attempt, wait_exponential


class AdpWorkforceManagerResource(ConfigurableResource):
    subdomain: str
    app_key: str
    client_id: str
    client_secret: str
    username: str
    password: str

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr()
    _refresh_token: str = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)
        self._base_url = f"https://{self.subdomain}.mykronos.com/api"

        self._session.headers["appkey"] = self.app_key

        self._authenticate(grant_type="password")

    def _authenticate(self, grant_type):
        self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self._session.headers.pop(
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

        response = self._session.post(
            f"{self._base_url}/authentication/access_token", data=payload
        )

        response.raise_for_status()
        response_data = response.json()

        self._refresh_token = response_data["refresh_token"]
        self._session.headers["Content-Type"] = "application/json"
        self._session.headers["Authorization"] = (
            "Bearer " + response_data["access_token"]
        )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _request(self, method, url, **kwargs):
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            self._log.exception(e)

            if response.status_code == 401:
                self._authenticate(grant_type="refresh_token")
                self._request(method=method, url=url, **kwargs)
            else:
                raise exceptions.HTTPError(response.text) from e

    def _get_url(self, endpoint, *args):
        return f"{self._base_url}/{endpoint}" + ("/" + "/".join(args) if args else "")

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(*args, endpoint=endpoint)
        self._log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def post(self, endpoint, *args, **kwargs):
        url = self._get_url(*args, endpoint=endpoint)
        self._log.debug(f"POST: {url}")

        return self._request(method="POST", url=url, **kwargs)
