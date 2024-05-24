import time

from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class OvergradResource(ConfigurableResource):
    api_key: str
    api_version: str = "v1"
    page_limit: int = 20

    _base_url: str = PrivateAttr(default="https://api.overgrad.com/api")
    _session: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._session.headers["ApiKey"] = self.api_key

    def _get_url(self, path, *args):
        versioned_url = f"{self._base_url}/{self.api_version}"
        if args:
            return f"{versioned_url}/{path}/{'/'.join(args)}"
        else:
            return f"{versioned_url}/{path}"

    def _request(self, method, url, **kwargs):
        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except exceptions.HTTPError as e:
            self.get_resource_context().log.exception(e)  # pyright: ignore[reportOptionalMemberAccess]
            raise exceptions.HTTPError(response.text) from e

    def get(self, path, *args, **kwargs):
        url = self._get_url(*args, path=path)
        self.get_resource_context().log.debug(f"GET: {url}")  # pyright: ignore[reportOptionalMemberAccess]

        return self._request(method="GET", url=url, **kwargs)

    def get_list(self, path, *args, **kwargs):
        context = self.get_resource_context()
        kwargs["params"] = {"limit": self.page_limit}

        page = 1
        data = []
        while True:
            kwargs["params"].update({"page": page})

            response_json: dict = self.get(path, *args, **kwargs).json()

            data.extend(response_json.pop("data"))
            context.log.debug(response_json)  # pyright: ignore[reportOptionalMemberAccess]

            if page == response_json["total_pages"]:
                break
            else:
                page += 1

                # Overgrad's API limits users to making 60 requests per minute
                # and 1000 requests per hour
                time.sleep(1)

        return data
