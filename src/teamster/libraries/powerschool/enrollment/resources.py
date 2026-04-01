from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class PowerSchoolEnrollmentResource(BaseHTTPResource):
    api_key: str
    api_version: str = "v1"
    page_size: int = 50

    def _setup_session(self) -> None:
        self._base_url = "https://registration.powerschool.com/api"
        self._session.auth = (self.api_key, "")

    def _get_url(self, *parts: str) -> str:
        return self._base_url + "/" + self.api_version + "/" + "/".join(parts)

    def list(self, endpoint: str, **kwargs) -> list[dict[str, Any]]:
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
