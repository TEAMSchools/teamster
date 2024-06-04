import json

from bs4 import BeautifulSoup, Tag
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from requests import Response, Session, exceptions


class MClassResource(ConfigurableResource):
    username: str
    password: str

    _base_url: str = PrivateAttr(default="https://mclass.amplify.com")
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

        portal_redirect = self.get(path="reports/myReports")

        soup = BeautifulSoup(markup=portal_redirect.text, features="html.parser")

        kc_form_login = _check.inst(
            obj=soup.find(name="form", id="kc-form-login"), ttype=Tag
        )

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
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except exceptions.HTTPError as e:
            self._log.exception(e)
            raise exceptions.HTTPError(response.text) from e
        except Exception as e:
            raise Exception from e

    def get(self, path, *args, **kwargs):
        url = self._get_url(*args, path=path)
        self._log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def post(self, path, data: dict | None = None, *args, **kwargs):
        if data is None:
            data = {}

        url = self._get_url(*args, path=path)
        self._log.debug(f"POST: {url}")

        for k, v in data.items():
            if isinstance(v, dict):
                data[k] = json.dumps(v)

        return self._request(method="POST", url=url, data=data, **kwargs)
