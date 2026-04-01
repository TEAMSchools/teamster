from typing import Any, cast

from oauthlib.oauth2 import BackendApplicationClient
from requests import Response
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from teamster.libraries.http.pagination import paginate_offset
from teamster.libraries.http.resources import BaseHTTPResource


class CoupaResource(BaseHTTPResource):
    """HTTP resource for the Coupa procurement and spend management API."""

    instance_url: str
    client_id: str
    client_secret: str
    scope: list[str]

    def _setup_session(self) -> None:
        """Configure base URL and obtain an OAuth2 Bearer token via client credentials."""
        self._base_url = f"https://{self.instance_url}"

        self._session = OAuth2Session(
            # trunk-ignore(pyright/reportArgumentType): scope is list[str], API expects str
            client=BackendApplicationClient(client_id=self.client_id, scope=self.scope)
        )

        token_dict = self._session.fetch_token(
            token_url=f"{self._base_url}/oauth2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

        self._session.headers["Authorization"] = "Bearer " + token_dict["access_token"]
        self._session.headers["Accept"] = "application/json"

    @property
    def oauth_session(self) -> OAuth2Session:
        """Return the underlying OAuth2Session for direct use."""
        return cast(OAuth2Session, self._session)

    def _get_url(self, *parts: str) -> str:
        """Return ``/<instance_url>/api/<parts>`` URL."""
        return self._base_url + "/api/" + "/".join(parts)

    def list(self, resource: str, **kwargs) -> list[dict[str, Any]]:
        """Return all records for a resource using offset-based pagination.

        Args:
            resource: API resource path segment.
            **kwargs: Additional keyword arguments forwarded to ``get``.

        Returns:
            Flat list of all record dicts across all pages.
        """
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(resource, params=params, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()

        for page_records in paginate_offset(fetch_page, extract_records, page_size=50):
            all_data.extend(page_records)

        return all_data
