from teamster.libraries.http.resources import BaseHTTPResource


class SmartRecruitersResource(BaseHTTPResource):
    smart_token: str

    def _setup_session(self) -> None:
        self._base_url = "https://api.smartrecruiters.com"
        self._session.headers["X-SmartToken"] = self.smart_token
