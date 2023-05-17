from dagster import ConfigurableResource
from requests import Session, exceptions


class WorkforceManagerResource(ConfigurableResource):
    subdomain: str
    app_key: str
    client_id: str
    client_secret: str
    username: str
    password: str

    def authenticate(self, refresh_token=None):
        self.client.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self.client.headers.pop("Authorization", "")  # remove existing auth for refresh

        if refresh_token is not None:
            payload = {
                **self.authentication_payload,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        else:
            payload = {
                **self.authentication_payload,
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
            }

        response = self.client.post(
            f"{self.base_url}/authentication/access_token", data=payload
        )

        response.raise_for_status()

        self.access_token = response.json()

        self.client.headers["Content-Type"] = "application/json"
        self.client.headers["Authorization"] = (
            "Bearer " + self.access_token["access_token"]
        )

    def setup_for_execution(self):
        self.client = Session()
        self.base_url = f"https://{self.subdomain}.mykronos.com/api"
        self.authentication_payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "auth_chain": "OAuthLdapService",
        }

        self.client.headers["appkey"] = self.app_key

        self.authenticate()

    def request(self, method, endpoint, **kwargs):
        try:
            response = self.client.request(
                method=method, url=f"{self.base_url}/{endpoint}", **kwargs
            )

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            context = self.get_resource_context()
            context.log.error(e)

            if response.status_code == 401:
                self.authenticate(refresh_token=self.access_token["refresh_token"])
                self.request(method, endpoint, **kwargs)
            else:
                raise exceptions.HTTPError(response.text) from e
