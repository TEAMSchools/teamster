from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError


class SmartRecruitersResource(ConfigurableResource):
    smart_token: str

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="https://api.smartrecruiters.com")
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)
        self._session.headers["X-SmartToken"] = self.smart_token

    def _get_url(self, endpoint, *args):
        return f"{self._base_url}/{endpoint}" + ("/" + "/".join(args) if args else "")

    def _request(self, method, url, **kwargs):
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.exception(e)
            raise HTTPError(response.text) from e

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(*args, endpoint=endpoint)
        self._log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def post(self, endpoint, *args, **kwargs):
        url = self._get_url(*args, endpoint=endpoint)
        self._log.debug(f"POST: {url}")

        return self._request(
            method="POST", url=self._get_url(*args, endpoint=endpoint), **kwargs
        )
