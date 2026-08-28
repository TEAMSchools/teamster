import copy
from typing import NoReturn

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout
from requests_oauthlib import OAuth2Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class GrowIncompleteResponseError(Exception):
    """Raised when the Grow API reports a non-zero count but returns no data,
    or when the total returned data length doesn't match the reported count.

    This is an upstream API flake (Grow occasionally reports records exist but
    returns an empty page), not an application bug. Recoverable via retry.
    """


class GrowAPIError(Exception):
    """Raised when the Grow API returns a non-2xx HTTP status.

    Carries the response body in ``args[0]`` for downstream error reporting.
    """


class GrowServerError(GrowAPIError):
    """Raised when a request to the Grow API fails transiently.

    Covers a 5xx response and a connection-level failure (refused, reset, DNS,
    timeout) on an idempotent request. An upstream flake, not an application
    bug, so it is recoverable via retry. POST is excluded: the create may have
    landed server-side, so retrying it risks a duplicate record.
    """


class GrowResource(ConfigurableResource):
    client_id: str
    client_secret: str
    district_id: str
    api_response_limit: int = 100

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="https://grow-api.leveldata.com")
    _default_params: dict = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)

        self._default_params = {
            "limit": self.api_response_limit,
            "district": self.district_id,
            "skip": 0,
        }

        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._get_access_token()["access_token"],
            }
        )

    def _get_access_token(self) -> dict:
        oauth = OAuth2Session(client=BackendApplicationClient(client_id=self.client_id))

        return oauth.fetch_token(
            token_url=f"{self._base_url}/auth/client/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

    def _get_url(self, endpoint: str, *args: str) -> str:
        return f"{self._base_url}/external/{endpoint}" + (
            "/" + "/".join(args) if args else ""
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=5, max=30),
        retry=retry_if_exception_type(GrowServerError),
        reraise=True,
    )
    def _request(self, method: str, url: str, **kwargs) -> Response:
        try:
            response = self._session.request(method=method, url=url, **kwargs)
        except (RequestsConnectionError, Timeout) as e:
            self._raise_request_error(
                message=str(e), cause=e, transient=method != "POST"
            )

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._raise_request_error(
                message=response.text,
                cause=e,
                transient=response.status_code >= 500 and method != "POST",
            )

    def _raise_request_error(
        self, message: str, cause: Exception, *, transient: bool
    ) -> NoReturn:
        """Raise the retryable or terminal error for a failed request.

        Keeps the severity decision in one place: a transient failure logs at
        WARNING, since the retry above recovers it and an ERROR would file a
        false-positive GCP Error Reporting group.
        """
        if transient:
            self._log.warning(msg=message)
            raise GrowServerError(message) from cause

        self._log.error(msg=message)
        raise GrowAPIError(message) from cause

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=5, max=30),
        retry=retry_if_exception_type(GrowIncompleteResponseError),
        reraise=True,
    )
    def get(self, endpoint: str, *args: str, **kwargs) -> dict:
        url = self._get_url(endpoint, *args)
        params = copy.deepcopy(self._default_params)

        params.update(kwargs)

        if args:
            self._log.debug(f"GET: {url}\nPARAMS: {params}")
            response_json = self._request(method="GET", url=url, params=params).json()

            # mock paginated response format
            return {
                "count": 1,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": [response_json],
            }
        else:
            data = []
            len_data = 0

            response = {
                "count": 0,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": data,
            }

            while True:
                self._log.debug(f"GET: {url}\nPARAMS: {params}")
                response_json = self._request(
                    method="GET", url=url, params=params
                ).json()

                count = response_json["count"]

                if "data" in response_json:
                    data.extend(response_json["data"])
                else:
                    self._log.error(msg="Missing 'data' key in response")
                    break

                len_data = len(data)

                self._log.debug(f"{len_data}/{count} records")

                if len_data >= count:
                    break
                elif len_data == 0 and count > 0:
                    raise GrowIncompleteResponseError(
                        "API returned an incomplete response"
                    )
                else:
                    params["skip"] += params["limit"]

            response["count"] = count

            if len_data != count:
                raise GrowIncompleteResponseError("API returned an incomplete response")
            else:
                return response

    def post(self, endpoint: str, *args: str, **kwargs) -> dict:
        url = self._get_url(endpoint, *args)

        self._log.debug(f"POST: {url}")
        return self._request(method="POST", url=url, **kwargs).json()

    def put(self, endpoint: str, *args: str, **kwargs) -> dict:
        url = self._get_url(endpoint, *args)

        self._log.debug(f"PUT: {url}")
        return self._request(method="PUT", url=url, **kwargs).json()

    def delete(self, endpoint: str, *args: str) -> dict:
        url = self._get_url(endpoint, *args)

        self._log.debug(f"DELETE: {url}")
        return self._request(method="DELETE", url=url).json()
