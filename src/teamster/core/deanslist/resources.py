import gc

import yaml
from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class DeansListResource(ConfigurableResource):
    subdomain: str
    api_key_map: str

    _client: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr()
    _api_key_map: dict = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._base_url = f"https://{self.subdomain}.deanslistsoftware.com/api"

        with open(self.api_key_map) as f:
            self._api_key_map = yaml.safe_load(f)["api_key_map"]

        return super().setup_for_execution(context)

    def _get_url(self, api_version, endpoint, *args):
        if api_version == "beta":
            return (
                f"{self._base_url}/{api_version}/export/get-{endpoint}"
                f"{'-data' if endpoint in ['behavior', 'homework', 'comm'] else ''}"
                ".php"
            )
        elif args:
            return f"{self._base_url}/{api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{api_version}/{endpoint}"

    def _request(self, method, url, params, **kwargs):
        context = self.get_resource_context()

        try:
            response = self._client.request(
                method=method, url=url, params=params, **kwargs
            )

            response.raise_for_status()
            return response
        except exceptions.HTTPError as e:
            context.log.error(e)
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

    def get(self, api_version, endpoint, school_id, params, *args, **kwargs):
        context = self.get_resource_context()

        url = self._get_url(api_version=api_version, endpoint=endpoint, *args)

        context.log.info(f"GET:\t{url}\nSCHOOL_ID:\t{school_id}\nPARAMS:\t{params}")

        params["apikey"] = self._api_key_map[school_id]

        response = self._request(method="GET", url=url, params=params, **kwargs)

        response.raise_for_status()

        return self._parse_response(response)
