from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session


class CoupaResource(ConfigurableResource):
    instance_url: str
    client_id: str
    client_secret: str
    scope: list[str]

    _service_root: str = PrivateAttr()
    _session: OAuth2Session = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._service_root = f"https://{self.instance_url}"
        self._log = check.not_none(value=context.log)

        # instantiate client
        self._session = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id, scope=self.scope)
        )

        # authorize client
        token_dict = self._session.fetch_token(
            token_url=f"{self._service_root}/oauth2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

        self._session.headers["Authorization"] = "Bearer " + token_dict["access_token"]
        self._session.headers["Accept"] = "application/json"

    def _get_url(self, resource: str, id: int | None) -> str:
        return f"{self._service_root}/api/{resource}" + (f"/{id}" if id else "")

    def _request(
        self, method: str, resource: str, id: int | None, **kwargs
    ) -> Response:
        url = self._get_url(resource=resource, id=id)

        self._log.debug(msg=f"{method} {url}\n{kwargs}")
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise e

    def get(self, resource: str, id: int | None = None, **kwargs):
        return self._request(method="GET", resource=resource, id=id, **kwargs)

    def put(self, resource: str, id: int, **kwargs):
        return self._request(method="PUT", resource=resource, id=id, **kwargs)

    def post(self, resource: str, **kwargs):
        return self._request(method="POST", resource=resource, **kwargs)

    def list(self, resource, **kwargs):
        all_data = []
        offset = 0

        while True:
            kwargs.update({"params": {"offset": offset}})

            data = self.get(resource=resource, **kwargs).json()

            if data:
                all_data.extend(data)
                offset += 50
            else:
                return all_data
