from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError


class PowerSchoolEnrollmentResource(ConfigurableResource):
    api_key: str
    api_version: str = "v1"
    page_size: int = 50

    _base_url: str = PrivateAttr(default="https://registration.powerschool.com/api")
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._session.auth = (self.api_key, "")

    def _get_url(self, endpoint, *args):
        if args:
            return f"{self._base_url}/{self.api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{self.api_version}/{endpoint}"

    def _request(self, method, url, **kwargs):
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.exception(e)
            raise HTTPError(response.text) from e

    def _parse_response(self, response):
        return response.json()

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint, *args)

        response = self._request(method="GET", url=url, **kwargs)

        return self._parse_response(response)

    def list(self, endpoint, **kwargs) -> list[dict]:
        page = 1
        all_records = []

        params = {"pagesize": self.page_size}

        while True:
            params.update({"page": page})

            metadata, records = self.get(
                endpoint=endpoint, params=params, **kwargs
            ).values()

            self._log.debug(metadata)
            all_records.extend(records)

            if page == metadata["pageCount"]:
                break
            else:
                page += 1

        return all_records
