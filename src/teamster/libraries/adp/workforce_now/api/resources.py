import time

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


class AdpWorkforceNowError(Exception):
    """Non-retryable ADP Workforce Now API error (deterministic 4xx response)."""


class AdpWorkforceNowResource(ConfigurableResource):
    client_id: str
    client_secret: str
    cert_filepath: str
    key_filepath: str
    masked: bool = True

    _service_root: str = PrivateAttr(default="https://api.adp.com")
    _session: OAuth2Session = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)

        # instantiate client
        self._session = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id)
        )
        self._session.cert = (self.cert_filepath, self.key_filepath)

        # authorize client
        token_dict = self._fetch_access_token()

        access_token = token_dict.get("access_token")

        self._session.headers["Authorization"] = f"Bearer {access_token}"

        if not self.masked:
            self._session.headers["Accept"] = "application/json;masked=false"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=10, max=60),
        retry=retry_if_exception_type((RequestsConnectionError, Timeout, HTTPError)),
    )
    def _fetch_access_token(self) -> dict:
        return self._session.fetch_token(
            # trunk-ignore(bandit/B106)
            token_url="https://accounts.adp.com/auth/oauth/v2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=10, max=60),
        retry=retry_if_exception_type((RequestsConnectionError, Timeout, HTTPError)),
    )
    def _request(self, method: str, url: str, **kwargs) -> Response:
        kwargs.setdefault("timeout", (10, 60))
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()

            # https://developers.adp.com/learn/key-concepts/access-tokens
            # Your application should limit access to under 300 times in a 60 second
            # period, with no more than 50 concurrent requests in any time. ADP will
            # throttle your requests when this limit is exceeded. Then, return a
            # response of HTTP 429 for too many requests.
            time.sleep(60 / 300)

            return response
        except HTTPError as e:
            # 429 (rate limited) and 5xx (server-side) errors are transient;
            # re-raise the HTTPError so tenacity retries with backoff. Check the
            # status code *before* parsing the body: gateway 5xx responses (e.g.
            # a 504 HTML page) are not JSON, and JSONDecodeError is not in the
            # retry predicate, so parsing here would convert a retryable error
            # into a non-retryable one.
            #
            # ADP's gateway also returns a transient "default backend - 404" when
            # it briefly has no healthy backend (a load-balancer signature, seen
            # mid-pagination). That is distinct from a genuine resource 404 —
            # treat only the gateway variant as retryable so a real 404 still
            # fails fast.
            body = response.text
            is_transient_gateway_404 = (
                response.status_code == 404 and "default backend" in body.lower()
            )
            if (
                response.status_code == 429
                or response.status_code >= 500
                or is_transient_gateway_404
            ):
                self._log.warning(msg=body)
                raise

            # other 4xx are deterministic client errors — surface a specific
            # exception (never a bare Exception) and do not retry. Guard the JSON
            # parse: a 4xx body may also be non-JSON.
            try:
                detail = response.json()
            except JSONDecodeError:
                detail = response.text

            self._log.error(msg=detail)
            raise AdpWorkforceNowError(detail) from e

    def post(
        self, endpoint: str, subresource: str, verb: str, payload: dict
    ) -> Response:
        return self._request(
            method="POST",
            url=f"{self._service_root}/{endpoint}.{subresource}.{verb}",
            json=payload,
        )

    def get(self, endpoint: str, params: dict | None = None) -> Response:
        if params is None:
            params = {}

        return self._request(
            method="GET", url=f"{self._service_root}/{endpoint}", params=params
        )

    def get_records(self, endpoint: str, params: dict | None = None) -> list[dict]:
        page_size = 100
        all_records = []

        endpoint_name = endpoint.split("/")[-1]

        if params is None:
            params = {}

        params.update({"$top": page_size, "$skip": 0})

        while True:
            self._log.debug(msg=params)
            response = self.get(endpoint=endpoint, params=params)

            if response.status_code == 204:
                break

            response_json = response.json()[endpoint_name]

            all_records.extend(response_json)
            params.update({"$skip": params["$skip"] + page_size})

        return all_records
