import json

from bs4 import BeautifulSoup, Tag
from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class MClassResource(ConfigurableResource):
    username: str
    password: str

    _base_url: str = PrivateAttr(default="https://mclass.amplify.com")
    _session: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        portal_redirect = self.get(path="reports/myReports")

        soup = BeautifulSoup(markup=portal_redirect.text, features="html.parser")

        kc_form_login: Tag = soup.find(name="form", id="kc-form-login")  # type: ignore

        self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self._request(
            method="POST",
            url=kc_form_login.attrs["action"],
            data={"username": self.username, "password": self.password},
        )

    def _get_url(self, path, *args):
        if args:
            return f"{self._base_url}/{path}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{path}"

    def _request(self, method, url, **kwargs):
        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            self.get_resource_context().log.exception(e)

            raise exceptions.HTTPError(response.text) from e

    def get(self, path, *args, **kwargs):
        url = self._get_url(*args, path=path)
        self.get_resource_context().log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def post(self, path, data: dict | None = None, *args, **kwargs):
        if data is None:
            data = {}

        url = self._get_url(*args, path=path)
        self.get_resource_context().log.debug(f"POST: {url}")

        for k, v in data.items():
            if isinstance(v, dict):
                data[k] = json.dumps(v)

        return self._request(method="POST", url=url, data=data, **kwargs)
