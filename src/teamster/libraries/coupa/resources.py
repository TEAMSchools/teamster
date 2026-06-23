from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, JSONDecodeError, Timeout
from requests_oauthlib import OAuth2Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class CoupaError(Exception):
    """Non-retryable Coupa API error (deterministic 4xx response)."""


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
            # trunk-ignore(pyright/reportArgumentType)
            client=BackendApplicationClient(client_id=self.client_id, scope=self.scope)
        )

        # authorize client
        token_dict = self._fetch_access_token()

        self._session.headers["Authorization"] = "Bearer " + token_dict["access_token"]
        self._session.headers["Accept"] = "application/json"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=10, max=60),
        retry=retry_if_exception_type((RequestsConnectionError, Timeout, HTTPError)),
    )
    def _fetch_access_token(self) -> dict:
        return self._session.fetch_token(
            token_url=f"{self._service_root}/oauth2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

    def _get_url(self, resource: str, id: int | None) -> str:
        return f"{self._service_root}/api/{resource}" + (f"/{id}" if id else "")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=10, max=60),
        retry=retry_if_exception_type((RequestsConnectionError, Timeout, HTTPError)),
    )
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
            # 429 (rate limited) and 5xx (server-side) errors are transient;
            # re-raise the HTTPError so tenacity retries with backoff.
            if response.status_code == 429 or response.status_code >= 500:
                self._log.warning(msg=response.text)
                raise

            # other 4xx are deterministic client errors — surface a specific
            # exception (never a bare Exception) and do not retry. Guard the JSON
            # parse: a 4xx body may not be JSON.
            try:
                detail = response.json()
            except JSONDecodeError:
                detail = response.text

            self._log.error(msg=detail)
            raise CoupaError(detail) from e

    def get(self, resource: str, id: int | None = None, **kwargs) -> Response:
        return self._request(method="GET", resource=resource, id=id, **kwargs)

    def put(self, resource: str, id: int, **kwargs) -> Response:
        return self._request(method="PUT", resource=resource, id=id, **kwargs)

    def post(self, resource: str, **kwargs) -> Response:
        return self._request(method="POST", resource=resource, **kwargs)

    def list(self, resource: str, **kwargs) -> list[dict]:
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
