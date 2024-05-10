import gc

from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class PowerSchoolEnrollmentResource(ConfigurableResource):
    api_key: str
    api_version: str = "v1"

    _base_url: str = PrivateAttr(default="https://secure.infosnap.com/api")
    _client: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None: ...

    def _get_url(self, endpoint, *args):
        if args:
            return f"{self._base_url}/{self.api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{self.api_version}/{endpoint}"

    def _request(self, method, url, params, **kwargs):
        context = self.get_resource_context()

        try:
            response = self._client.request(
                method=method, url=url, params=params, **kwargs
            )

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            context.log.exception(e)
            raise exceptions.HTTPError(response.text) from e

    def _parse_response(self, response):
        response_json = response.json()
        del response
        gc.collect()

        row_count = response_json.get("rowcount", 0)
        deleted_row_count = response_json.get("deleted_rowcount", 0)

        total_row_count = row_count + deleted_row_count

        data = response_json.get("data", [])
        deleted_data = response_json.get("deleted_data", [])
        for d in deleted_data:
            d["is_deleted"] = True

        del response_json
        gc.collect()

        all_data = data + deleted_data

        return {"row_count": total_row_count, "data": all_data}

    def get(self, endpoint, params, *args, **kwargs):
        url = self._get_url(endpoint, *args)

        response = self._request(method="GET", url=url, params=params, **kwargs)

        return self._parse_response(response)
