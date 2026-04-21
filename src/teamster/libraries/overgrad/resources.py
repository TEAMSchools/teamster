import time

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class OvergradResource(ConfigurableResource):
    api_key: str
    api_version: str = "v1"
    page_limit: int = 20
    request_timeout: float = 60.0

    _base_url: str = PrivateAttr(default="https://api.overgrad.com/api")
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._session.headers["ApiKey"] = self.api_key

    def _get_url(self, path: str, *args: str) -> str:
        versioned_url = f"{self._base_url}/{self.api_version}"

        if args:
            return f"{versioned_url}/{path}/{'/'.join(args)}"
        else:
            return f"{versioned_url}/{path}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=60),
        retry=retry_if_exception_type(HTTPError),
    )
    def _request(self, method: str, url: str, **kwargs) -> Response:
        response = self._session.request(
            method=method, url=url, timeout=self.request_timeout, **kwargs
        )

        try:
            response.raise_for_status()
            return response
        except HTTPError:
            if response.status_code == 429 or response.status_code >= 500:
                raise  # retryable via tenacity

            raise Exception(response.text) from None

    def get(self, path: str, *args: str, **kwargs) -> Response:
        url = self._get_url(path, *args)
        self._log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def list(self, path: str, *args: str, **kwargs) -> list[dict]:
        kwargs["params"] = {"limit": self.page_limit}

        page = 1
        data = []
        while True:
            kwargs["params"].update({"page": page})

            response_json: dict = self.get(path, *args, **kwargs).json()

            data.extend(response_json.pop("data"))
            self._log.debug(response_json)

            if page == response_json["total_pages"]:
                break
            else:
                page += 1

                # Overgrad's API limits users to making 60 requests per minute and 1000
                # requests per hour
                # - increased past 1 req/sec becase we still get 429 errors
                time.sleep(1.5)

        return data
