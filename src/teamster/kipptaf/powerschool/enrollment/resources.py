from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class PowerSchoolEnrollmentResource(ConfigurableResource):
    api_key: str
    api_version: str = "v1"

    _base_url: str = PrivateAttr(default="https://registration.powerschool.com/api")
    _client: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client.auth = (self.api_key, "")

    def _get_url(self, endpoint, *args):
        if args:
            return f"{self._base_url}/{self.api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{self.api_version}/{endpoint}"

    def _request(self, method, url, **kwargs):
        context = self.get_resource_context()

        try:
            response = self._client.request(method=method, url=url, **kwargs)
            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            context.log.exception(e)
            raise exceptions.HTTPError(response.text) from e

    def _parse_response(self, response):
        return response.json()

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint, *args)

        response = self._request(method="GET", url=url, **kwargs)

        return self._parse_response(response)

    def get_all_records(self, endpoint, *args, **kwargs):
        records = []
        page = 1

        while True:
            kwargs["params"] = {"page": page}

            response = self.get(endpoint, *args, **kwargs)

            records.extend(response["records"])

            if page == response["metaData"]["pageCount"]:
                break
            else:
                page += 1

        return records
