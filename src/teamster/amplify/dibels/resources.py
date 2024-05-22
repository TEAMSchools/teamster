from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class DibelsDataSystemResource(ConfigurableResource):
    username: str
    password: str

    _base_url: str = PrivateAttr(default="https://dibels.amplify.com")
    _session: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._session.headers["Content-Type"] = "application/x-www-form-urlencoded"
        self._request(
            method="POST",
            url=f"{self._base_url}/user/login",
            data={"name": self.username, "password": self.password, "login": "Login"},
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
            self.get_resource_context().log.exception(e)  # pyright: ignore[reportOptionalMemberAccess]
            raise exceptions.HTTPError(response.text) from e

    def get(self, path, *args, **kwargs):
        url = self._get_url(*args, path=path)
        self.get_resource_context().log.debug(f"GET: {url}")  # pyright: ignore[reportOptionalMemberAccess]

        return self._request(method="GET", url=url, **kwargs)

    def report(
        self,
        report,
        scope,
        district,
        grade,
        start_year,
        end_year,
        assessment,
        assessment_period,
        student_filter,
        delimiter,
        growth_measure,
        fields: list[int] | None = None,
    ):
        if fields is None:
            fields = []

        response = self.get(
            path="reports/report.php",
            params={
                "report": report,
                "Scope": scope,
                "district": district,
                "Grade": grade,
                "StartYear": start_year,
                "EndYear": end_year,
                "Assessment": assessment,
                "AssessmentPeriod": assessment_period,
                "StudentFilter": student_filter,
                "GrowthMeasure": growth_measure,
                "Delimiter": delimiter,
                "Fields": fields,
            },
        )

        return response
