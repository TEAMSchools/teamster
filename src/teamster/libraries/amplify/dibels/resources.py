from bs4 import BeautifulSoup, Tag
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from requests import Session, exceptions


class DibelsDataSystemResource(ConfigurableResource):
    username: str
    password: str

    _base_url: str = PrivateAttr(default="https://dibels.amplify.com")
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)
        self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"

        response = self._request(method="GET", url=f"{self._base_url}/user/login")

        soup = BeautifulSoup(markup=response.text, features="html.parser")

        csrf_token = _check.inst(
            obj=soup.find(name="meta", attrs={"name": "csrf-token"}), ttype=Tag
        )

        self._request(
            method="POST",
            url=f"{self._base_url}/user/login",
            data={
                "_token": csrf_token.get(key="content"),
                "username": self.username,
                "password": self.password,
                "login": "Login",
            },
        )

    def _get_url(self, path, *args):
        if args:
            return f"{self._base_url}/{path}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{path}"

    def _request(self, method, url, **kwargs):
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except exceptions.HTTPError as e:
            self._log.exception(e)
            raise exceptions.HTTPError(response.text) from e

    def get(self, path, *args, **kwargs):
        url = self._get_url(*args, path=path)
        self._log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def report(self, report, scope, district, grade, assessment, delimiter, **kwargs):
        response = self.get(
            path="reports/report.php",
            params={
                "report": report,
                "Scope": scope,
                "district": district,
                "Grade": grade,
                "Assessment": assessment,
                "Delimiter": delimiter,
                **kwargs,
            },
        )

        soup = BeautifulSoup(markup=response.text, features="html.parser")

        csv_link = _check.inst(
            obj=soup.find(name="a", attrs={"class": "csv-link"}), ttype=Tag
        )

        return self._request(method="GET", url=csv_link.get(key="href"))
