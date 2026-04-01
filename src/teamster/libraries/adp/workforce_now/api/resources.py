from typing import Any, cast

from oauthlib.oauth2 import BackendApplicationClient
from requests import Response
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from teamster.libraries.http.pagination import paginate_offset
from teamster.libraries.http.resources import BaseHTTPResource


class AdpWorkforceNowResource(BaseHTTPResource):
    client_id: str
    client_secret: str
    cert_filepath: str
    key_filepath: str
    masked: bool = True

    def _setup_session(self) -> None:
        self._base_url = "https://api.adp.com"

        self._session = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id)
        )
        self._session.cert = (self.cert_filepath, self.key_filepath)

        token_dict = self._session.fetch_token(
            # trunk-ignore(bandit/B106): token URL, not a password
            token_url="https://accounts.adp.com/auth/oauth/v2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

        self._session.headers["Authorization"] = (
            f"Bearer {token_dict.get('access_token')}"
        )

        if not self.masked:
            self._session.headers["Accept"] = "application/json;masked=false"

    @property
    def oauth_session(self) -> OAuth2Session:
        return cast(OAuth2Session, self._session)

    def get_records(
        self, endpoint: str, params: dict | None = None
    ) -> list[dict[str, Any]]:
        endpoint_name = endpoint.split("/")[-1]

        if params is None:
            params = {}

        all_records: list[dict[str, Any]] = []

        def fetch_page(page_params: dict) -> Response:
            merged = {**params, **page_params}
            self._log.debug(msg=merged)
            return self.get(endpoint, params=merged)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            if resp.status_code == 204:
                return []
            return resp.json()[endpoint_name]

        def is_last_page(resp: Response) -> bool:
            return resp.status_code == 204

        for page_records in paginate_offset(
            fetch_page,
            extract_records,
            page_size=100,
            offset_param="$skip",
            limit_param="$top",
            is_last_page=is_last_page,
        ):
            all_records.extend(page_records)

        return all_records
