from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class WorkforceManagerResource(ConfigurableResource):
    subdomain: str
    app_key: str
    client_id: str
    client_secret: str
    username: str
    password: str

    _client: Session = PrivateAttr()
    _base_url: str = PrivateAttr()
    _authentication_payload: dict = PrivateAttr()
    _access_token: dict = PrivateAttr()

    def authenticate(self, refresh_token=None):
        self._client.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self._client.headers.pop(
            "Authorization", ""
        )  # remove existing auth for refresh

        if refresh_token is not None:
            payload = {
                **self._authentication_payload,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        else:
            payload = {
                **self._authentication_payload,
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
            }

        response = self._client.post(
            f"{self._base_url}/authentication/access_token", data=payload
        )

        response.raise_for_status()

        self._access_token = response.json()

        self._client.headers["Content-Type"] = "application/json"
        self._client.headers["Authorization"] = (
            "Bearer " + self._access_token["access_token"]
        )

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client = Session()
        self._base_url = f"https://{self.subdomain}.mykronos.com/api"
        self._authentication_payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "auth_chain": "OAuthLdapService",
        }

        self._client.headers["appkey"] = self.app_key

        self.authenticate()

        return super().setup_for_execution(context)

    def request(self, method, endpoint, **kwargs):
        try:
            response = self._client.request(
                method=method, url=f"{self._base_url}/{endpoint}", **kwargs
            )

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            context = self.get_resource_context()
            context.log.error(e)

            if response.status_code == 401:
                self.authenticate(refresh_token=self._access_token["refresh_token"])
                self.request(method, endpoint, **kwargs)
            else:
                raise exceptions.HTTPError(response.text) from e
