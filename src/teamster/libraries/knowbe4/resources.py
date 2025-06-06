import time

from dagster import ConfigurableResource, DagsterLogManager
from dagster_shared import check
from pydantic import PrivateAttr
from requests import HTTPError, Response, Session


class KnowBe4Resource(ConfigurableResource):
    api_key: str
    server: str
    page_size: int = 100

    _service_root: str = PrivateAttr(default="https://{0}.api.knowbe4.com")
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context):
        self._log = check.not_none(value=context.log)
        self._service_root = self._service_root.format(self.server)
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"

    def _get_url(self, resource: str, id: int | None, api_version: str = "v1") -> str:
        return f"{self._service_root}/{api_version}/{resource}" + (
            f"/{id}" if id else ""
        )

    def _request(
        self, method: str, resource: str, id: int | None, **kwargs
    ) -> Response:
        url = self._get_url(resource=resource, id=id)

        self._log.debug(msg=f"{method} {url}\n{kwargs}")
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise e

    def get(self, resource: str, id: int | None = None, **kwargs):
        return self._request(method="GET", resource=resource, id=id, **kwargs)

    def list(self, resource, **kwargs):
        params = {"per_page": self.page_size} | kwargs.get("params", {})

        all_data = []
        page = 1

        while True:
            data = self.get(resource=resource, params={"page": page, **params}).json()

            if data:
                all_data.extend(data)
                page += 1
            else:
                return all_data

            # https://developer.knowbe4.com/rest/reporting#tag/Rate-Limiting
            # 2,000 requests per day plus the number of licensed users on your account.
            # The APIs may only be accessed four times per second. The API burst limit
            # is 50 requests per minute. Please note that the API bursts limits will
            # start around five (5) minutes and the API daily limit starts around
            # twenty-four (24) hours from the first API request.
            time.sleep(1 / 4)
