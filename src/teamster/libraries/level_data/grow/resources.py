import copy
from typing import Any

from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response
from requests_oauthlib import OAuth2Session

from teamster.libraries.http.pagination import paginate_offset
from teamster.libraries.http.resources import BaseHTTPResource


class GrowResource(BaseHTTPResource):
    """HTTP resource for the LevelData Grow performance management API."""

    client_id: str
    client_secret: str
    district_id: str
    api_response_limit: int = 100

    _default_params: dict = PrivateAttr()

    def _setup_session(self) -> None:
        """Configure base URL, default params, and obtain an OAuth2 Bearer token."""
        self._base_url = "https://grow-api.leveldata.com"

        self._default_params = {
            "limit": self.api_response_limit,
            "district": self.district_id,
            "skip": 0,
        }

        oauth = OAuth2Session(client=BackendApplicationClient(client_id=self.client_id))
        token_dict = oauth.fetch_token(
            token_url=f"{self._base_url}/auth/client/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token_dict['access_token']}",
            }
        )

    def _get_url(self, *parts: str) -> str:
        """Return ``/grow-api.leveldata.com/external/<parts>`` URL."""
        return self._base_url + "/external/" + "/".join(parts)

    # trunk-ignore(pyright/reportIncompatibleMethodOverride): Grow API returns dict, not Response
    def get(self, endpoint: str, *args: str, **kwargs) -> dict[str, Any]:
        """GET with pagination and response validation.

        Args:
            endpoint: API endpoint name.
            *args: If provided, treated as resource ID for single-resource fetch.
            **kwargs: Additional params merged into default params.
        """
        params = copy.deepcopy(self._default_params)
        params.update(kwargs)

        if args:
            self._log.debug(f"GET: {self._get_url(endpoint, *args)}")
            response = self._request(
                "GET", self._get_url(endpoint, *args), params=params
            )
            response_json = response.json()
            return {
                "count": 1,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": [response_json],
            }

        data: list[dict[str, Any]] = []
        count = 0

        def fetch_page(page_params: dict) -> Response:
            merged = {**params, **page_params}
            self._log.debug(f"GET: {self._get_url(endpoint)}\nPARAMS: {merged}")
            return self._request("GET", self._get_url(endpoint), params=merged)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            nonlocal count
            response_json = resp.json()
            count = response_json.get("count", 0)
            if "data" not in response_json:
                self._log.error(msg="Missing 'data' key in response")
                return []
            return response_json["data"]

        for page_records in paginate_offset(
            fetch_page,
            extract_records,
            page_size=self.api_response_limit,
            offset_param="skip",
            limit_param="limit",
        ):
            if not page_records and count > 0:
                raise Exception("API returned an incomplete response")
            data.extend(page_records)
            self._log.debug(f"{len(data)}/{count} records")

        if data and len(data) != count:
            raise Exception("API returned an incomplete response")

        return {
            "count": count,
            "limit": self._default_params["limit"],
            "skip": self._default_params["skip"],
            "data": data,
        }

    # trunk-ignore(pyright/reportIncompatibleMethodOverride): Grow API returns dict, not Response
    def post(self, endpoint: str, *args: str, **kwargs) -> dict[str, Any]:
        """Send a POST request and return the parsed JSON response.

        Args:
            endpoint: API endpoint name.
            *args: Additional path segments appended to the URL.
            **kwargs: Additional keyword arguments forwarded to ``_request``.

        Returns:
            Parsed JSON response dict.
        """
        url = self._get_url(endpoint, *args)
        self._log.debug(f"POST: {url}")
        return self._request("POST", url, **kwargs).json()

    # trunk-ignore(pyright/reportIncompatibleMethodOverride): Grow API returns dict, not Response
    def put(self, endpoint: str, *args: str, **kwargs) -> dict[str, Any]:
        """Send a PUT request and return the parsed JSON response.

        Args:
            endpoint: API endpoint name.
            *args: Additional path segments appended to the URL.
            **kwargs: Additional keyword arguments forwarded to ``_request``.

        Returns:
            Parsed JSON response dict.
        """
        url = self._get_url(endpoint, *args)
        self._log.debug(f"PUT: {url}")
        return self._request("PUT", url, **kwargs).json()

    # trunk-ignore(pyright/reportIncompatibleMethodOverride): Grow API returns dict, not Response
    def delete(self, endpoint: str, *args: str) -> dict[str, Any]:
        """Send a DELETE request and return the parsed JSON response.

        Args:
            endpoint: API endpoint name.
            *args: Additional path segments appended to the URL.

        Returns:
            Parsed JSON response dict.
        """
        url = self._get_url(endpoint, *args)
        self._log.debug(f"DELETE: {url}")
        return self._request("DELETE", url).json()
