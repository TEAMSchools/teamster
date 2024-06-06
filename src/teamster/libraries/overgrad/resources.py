import time

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError


class OvergradResource(ConfigurableResource):
    api_key: str
    api_version: str = "v1"
    page_limit: int = 20

    _base_url: str = PrivateAttr(default="https://api.overgrad.com/api")
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)
        self._session.headers["ApiKey"] = self.api_key

    def _get_url(self, path, *args):
        versioned_url = f"{self._base_url}/{self.api_version}"

        if args:
            return f"{versioned_url}/{path}/{'/'.join(args)}"
        else:
            return f"{versioned_url}/{path}"

    def _request(self, method, url, **kwargs):
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.exception(e)
            raise HTTPError(response.text) from e

    def get(self, path, *args, **kwargs):
        url = self._get_url(path, *args)
        self._log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def get_list(self, path, *args, **kwargs):
        kwargs["params"] = {"limit": self.page_limit}

        page = 1
        data = []
        while True:
            kwargs["params"].update({"page": page})

            response_json: dict = self.get(path, *args, **kwargs).json()

            data.extend(response_json.pop("data"))
            self._log.debug(response_json)

            if page == response_json["total_pages"]:
                break
            else:
                page += 1

                # Overgrad's API limits users to making 60 requests per minute
                # and 1000 requests per hour
                time.sleep(1)

        return data
