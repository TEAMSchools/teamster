from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class KnowBe4Resource(BaseHTTPResource):
    """HTTP resource for the KnowBe4 security awareness training API."""

    api_key: str
    server: str
    page_size: int = 100

    def _setup_session(self) -> None:
        """Configure base URL for the regional server and Bearer token auth."""
        self._base_url = f"https://{self.server}.api.knowbe4.com"
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"

    def _get_url(self, *parts: str) -> str:
        """Return ``/<server>.api.knowbe4.com/v1/<parts>`` URL."""
        return self._base_url + "/v1/" + "/".join(parts)

    def list(self, resource: str, **kwargs) -> list[dict[str, Any]]:
        """Return all records for a resource using page-based pagination.

        Args:
            resource: API resource path segment.
            **kwargs: Ignored; reserved for interface compatibility.

        Returns:
            Flat list of all record dicts across all pages.
        """
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(resource, params=params)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=self.page_size,
            page_param="page",
            size_param="per_page",
        ):
            all_data.extend(page_records)

        return all_data
