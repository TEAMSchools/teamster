import time
from typing import Any

from requests import Response
from requests.auth import HTTPBasicAuth

from teamster.libraries.http.pagination import paginate_cursor
from teamster.libraries.http.resources import BaseHTTPResource


class ZendeskResource(BaseHTTPResource):
    """HTTP resource for the Zendesk customer support REST API."""

    subdomain: str
    email: str
    token: str
    page_size: int = 100
    api_version: str = "v2"

    def _setup_session(self) -> None:
        """Configure base URL and HTTP Basic auth with email/token credentials."""
        self._base_url = f"https://{self.subdomain}.zendesk.com/api"
        self._session.headers["Content-Type"] = "application/json"
        self._session.auth = HTTPBasicAuth(
            username=f"{self.email}/token", password=self.token
        )

    def _get_url(self, *parts: str) -> str:
        """Return ``/<subdomain>.zendesk.com/api/<api_version>/<parts>`` URL."""
        return (
            self._base_url
            + "/"
            + self.api_version
            + "/"
            + "/".join(str(p) for p in parts if p)
        )

    def _get_retry_after(self, response: Response) -> float | None:
        """Parse Zendesk-specific rate-limit headers."""
        remaining = response.headers.get("ratelimit-remaining")
        if remaining is not None and int(remaining) <= 0:
            reset = response.headers.get("ratelimit-reset", "60")
            return max(float(reset) - time.time() + 1, 0.0)

        endpoint_header = response.headers.get("Zendesk-RateLimit-Endpoint", "")
        if endpoint_header:
            parts = endpoint_header.split(";")
            if int(parts[1].split("=")[1]) <= 0:
                return max(float(parts[2].split("=")[1]) - time.time() + 1, 0.0)

        return super()._get_retry_after(response)

    def list(self, resource: str, **kwargs) -> list[dict[str, Any]]:
        """Return all records for a resource using cursor-based pagination.

        Args:
            resource: API resource name used as the URL segment and response key.
            **kwargs: Supports ``params`` dict merged into initial page params.

        Returns:
            Flat list of all record dicts across all pages.
        """
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(resource, params=params)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()[resource]

        def extract_cursor(resp: Response) -> str | None:
            meta = resp.json().get("meta", {})
            if meta.get("has_more"):
                return meta.get("after_cursor")
            return None

        for page_records in paginate_cursor(
            fetch_page,
            extract_records,
            extract_cursor,
            page_params={"page[size]": self.page_size, **kwargs.get("params", {})},
        ):
            all_data.extend(page_records)

        return all_data
