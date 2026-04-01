from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class PowerSchoolEnrollmentResource(BaseHTTPResource):
    """HTTP resource for the PowerSchool Enrollment/Registration REST API."""

    api_key: str
    api_version: str = "v1"
    page_size: int = 50

    def _setup_session(self) -> None:
        """Configure base URL and HTTP Basic auth with the API key."""
        self._base_url = "https://registration.powerschool.com/api"
        self._session.auth = (self.api_key, "")

    def _get_url(self, *parts: str) -> str:
        """Return ``/api/<api_version>/<parts>`` URL."""
        return self._base_url + "/" + self.api_version + "/" + "/".join(parts)

    def list(self, endpoint: str, **kwargs) -> list[dict[str, Any]]:
        """Return all records for an endpoint using page-based pagination.

        Args:
            endpoint: API endpoint path segment.
            **kwargs: Additional keyword arguments forwarded to ``get``.

        Returns:
            Flat list of all record dicts across all pages.
        """
        all_records: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(endpoint, params=params, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            response_json = resp.json()
            metadata, records = response_json.values()
            self._log.debug(metadata)
            return records

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=self.page_size,
            size_param="pagesize",
        ):
            all_records.extend(page_records)

        return all_records
