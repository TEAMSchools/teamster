import time
from datetime import datetime, timedelta

import jwt
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import HTTPError, Response, Session
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)


def _is_retryable(exception: BaseException) -> bool:
    """Return True for transient faults worth a bounded retry.

    Two cases are retried:

    - A bare gateway ``403``. All four districts' contacts pulls fire
      simultaneously from one shared egress IP, so the Finalsite gateway returns
      a ``403`` (not a ``429``) once the concurrent load trips its per-source
      ceiling. The ``finalsite_api`` concurrency pool is the root-cause fix; this
      is defense-in-depth for a transient ``403``.
    - A connection error or connect/read timeout against the gateway.

    A ``429`` never reaches here — it is handled in-band (sleep on ``Retry-After``
    then retry). Other ``4xx``/``5xx`` are deterministic and fail fast.
    """
    if isinstance(exception, (RequestsConnectionError, Timeout)):
        return True

    return (
        isinstance(exception, HTTPError)
        and exception.response is not None
        and exception.response.status_code == 403
    )


class FinalsiteResource(ConfigurableResource):
    server: str
    credential_id: str
    secret: str
    api_version: str = "1"
    request_timeout: float = 60.0

    _service_root: str = PrivateAttr(
        default="https://{0}.fsenrollment.com/api/external"
    )
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._service_root = self._service_root.format(self.server)

        payload = {
            "sub": self.credential_id,
            "name": "Dagster",
            # Finalsite rejects any exp more than 60 minutes out; 55 leaves a
            # clock-skew margin while maximizing the pagination window.
            "exp": datetime.now() + timedelta(minutes=55),
        }

        token = jwt.encode(payload=payload, key=self.secret)

        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["X-Api-Version"] = self.api_version

    def _get_url(self, path: str, id: str | None) -> str:
        return f"{self._service_root}/{path}" + (f"/{id}" if id else "")

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=60),
        reraise=True,
    )
    def _request(self, method: str, path: str, id: str | None, **kwargs) -> Response:
        url = self._get_url(path=path, id=id)
        kwargs.setdefault("timeout", self.request_timeout)

        self._log.debug(msg=f"{method} {url}\n{kwargs}")
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except HTTPError:
            if response.status_code == 429:
                retry_after = float(response.headers["Retry-After"])

                self._log.warning(
                    f"Rate limited on {method} {path} "
                    f"({response.text.strip()}); retrying in {retry_after}s"
                )
                time.sleep(retry_after)

                return self._request(method=method, path=path, id=id, **kwargs)

            if response.status_code == 403:
                self._log.warning(
                    f"Forbidden (403) on {method} {path}: {response.text.strip()[:200]}"
                )
                raise

            self._log.error(response.text)
            raise

    def get(self, path: str, id: str | None = None, **kwargs) -> Response:
        return self._request(method="GET", path=path, id=id, **kwargs)

    def list(self, path: str, **kwargs) -> list[dict]:
        params = kwargs.get("params", {})

        all_data = []
        page = 0

        # The API exposes no total count/page count (cursor-only pagination), so
        # log a running tally per page to make long pulls observable at INFO.
        while True:
            response_json = self.get(path=path, params=params).json()

            records = response_json[path]
            all_data.extend(records)
            page += 1

            next_cursor = response_json.get("meta", {}).get("next_cursor")

            self._log.info(
                f"{path}: page {page} returned {len(records)} record(s); "
                f"{len(all_data)} accumulated"
                + ("; fetching next page" if next_cursor else "; final page")
            )

            if next_cursor:
                params["cursor"] = next_cursor
            else:
                break

        self._log.info(
            f"{path}: completed {page} page(s), {len(all_data)} total record(s)"
        )

        return all_data
