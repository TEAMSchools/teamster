import time

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import Field, PrivateAttr
from requests import Response, Session
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class OvergradResource(ConfigurableResource):
    api_key: str = Field(repr=False)
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
        retry=retry_if_exception_type((RequestsConnectionError, Timeout, HTTPError)),
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

    # defined before `list`, whose name shadows the builtin for later annotations
    def list_by_cursor(self, path: str) -> list[dict]:
        """Pull every record of a list endpoint that supports `updated_after`.

        Overgrad sorts list results by `updated_at` ascending, so a record
        edited mid-pull moves to the end and a page-number pull skips the
        record that slides into an already-read page. Paging on the last
        `updated_at` seen instead cannot skip: an edited record shows up again
        later. The boundary is inclusive, so the result repeats records;
        callers dedupe by `id`.
        """
        url = self._get_url(path)
        cursor: str | None = None
        page_number = 1

        data = []
        while True:
            params: dict[str, int | str] = {
                "limit": self.page_limit,
                "page": page_number,
            }

            if cursor is not None:
                params["updated_after"] = cursor

            response_json: dict = self._request(
                method="GET", url=url, params=params
            ).json()

            page = response_json.pop("data")
            data.extend(page)

            if cursor is None:
                self._log.info(f"GET: {url} {response_json}")

            if len(page) < self.page_limit:
                break

            # shortcut: a record with a null `updated_at` never matches
            # `updated_after` and is not pulled; none exist today, and one
            # ending a page fails the run here
            next_cursor = check.not_none(page[-1]["updated_at"])

            if next_cursor == cursor:
                # shortcut: a full page sharing one timestamp steps by page
                # number, so an edit inside that group mid-pull can still skip
                # a record; add an `id` tiebreak if 100+ record bulk updates appear
                page_number += 1
            else:
                cursor, page_number = next_cursor, 1

            # Overgrad's API limits users to making 60 requests per minute and 1000
            # requests per hour
            time.sleep(1.5)

        return data

    def list(self, path: str, *args: str, **kwargs) -> list[dict]:
        kwargs["params"] = {"limit": self.page_limit}

        url = self._get_url(path, *args)

        page = 1
        data = []
        while True:
            kwargs["params"].update({"page": page})

            response_json: dict = self._request(method="GET", url=url, **kwargs).json()

            data.extend(response_json.pop("data"))

            # no per-page logging: each Dagster log call is a synchronous event
            # write, and hundreds of pages turn slow writes into a max_runtime timeout
            if page == 1:
                self._log.info(f"GET: {url} {response_json}")

            # `>=`: an empty result reports total_pages 0, which `==` never reaches
            if page >= response_json["total_pages"]:
                break
            else:
                page += 1

                # Overgrad's API limits users to making 60 requests per minute and 1000
                # requests per hour
                # - increased past 1 req/sec becase we still get 429 errors
                time.sleep(1.5)

        return data
