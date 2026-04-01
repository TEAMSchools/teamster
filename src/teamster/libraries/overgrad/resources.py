from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class OvergradResource(BaseHTTPResource):
    """HTTP resource for the Overgrad college counseling platform API."""

    api_key: str
    api_version: str = "v1"
    page_limit: int = 20

    def _setup_session(self) -> None:
        """Configure base URL and ApiKey header auth."""
        self._base_url = "https://api.overgrad.com/api"
        self._session.headers["ApiKey"] = self.api_key

    def _get_url(self, *parts: str) -> str:
        """Return ``/api/<api_version>/<parts>`` URL."""
        return self._base_url + "/" + self.api_version + "/" + "/".join(parts)

    def list(self, path: str, *args: str, **kwargs) -> list[dict[str, Any]]:
        """Return all records for an endpoint using page-based pagination.

        Args:
            path: API endpoint path segment.
            *args: Additional path segments appended to the URL.
            **kwargs: Additional keyword arguments forwarded to ``get``.

        Returns:
            Flat list of all record dicts from the ``data`` key across all pages.
        """
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(path, *args, params=params, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            response_json = resp.json()
            self._log.debug({k: v for k, v in response_json.items() if k != "data"})
            return response_json["data"]

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=self.page_limit,
            page_param="page",
            size_param="limit",
        ):
            all_data.extend(page_records)

        return all_data
