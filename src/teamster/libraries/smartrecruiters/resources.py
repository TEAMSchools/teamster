from teamster.libraries.http.resources import BaseHTTPResource


class SmartRecruitersResource(BaseHTTPResource):
    """HTTP resource for the SmartRecruiters Reporting API."""

    smart_token: str

    def _setup_session(self) -> None:
        """Configure base URL and X-SmartToken header auth."""
        self._base_url = "https://api.smartrecruiters.com"
        self._session.headers["X-SmartToken"] = self.smart_token
