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
    _refresh_token: str = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client = Session()
        self._base_url = f"https://{self.subdomain}.mykronos.com/api"

        self._client.headers["appkey"] = self.app_key

        self.authenticate(grant_type="password")

        return super().setup_for_execution(context)

    def authenticate(self, grant_type):
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
                self.authenticate(grant_type="refresh_token")
                self.request(method, endpoint, **kwargs)
            else:
                raise exceptions.HTTPError(response.text) from e
