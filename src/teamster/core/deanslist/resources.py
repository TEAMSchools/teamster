import gc

import yaml
from dagster import Field, InitResourceContext, String, StringSource, resource
from requests import Session


class DeansList(Session):
    def __init__(
        self,
        logger: InitResourceContext.log,
        resource_config: InitResourceContext.resource_config,
    ):
        super().__init__()

        self.log = logger
        self.subdomain = resource_config["subdomain"]
        self.base_url = f"https://{self.subdomain}.deanslistsoftware.com/api"

        with open(resource_config["api_key_map"]) as f:
            self.api_key_map = yaml.safe_load(f)["api_key_map"]

    def _get_url(self, api_version, endpoint, *args):
        if api_version == "beta":
            return (
                f"{self.base_url}/{api_version}/export/get-{endpoint}"
                f"{'-data' if endpoint in ['behavior', 'homework', 'comm'] else ''}"
                ".php"
            )
        elif args:
            return f"{self.base_url}/{api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self.base_url}/{api_version}/{endpoint}"

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

    def get_endpoint(self, api_version, endpoint, school_id, *args, **kwargs):
        url = self._get_url(api_version=api_version, endpoint=endpoint, *args)

        self.log.info(f"GET: {url}\nSCHOOL_ID: {school_id}\nPARAMS: {kwargs}")

        kwargs["apikey"] = self.api_key_map[school_id]

        response = self.get(url=url, params=kwargs)
        response.raise_for_status()

        return self._parse_response(response)


@resource(
    config_schema={
        "subdomain": StringSource,
        "api_key_map": String,
        "api_version": Field(
            config=StringSource, default_value="v1", is_required=False
        ),
    }
)
def deanslist_resource(context: InitResourceContext):
    return DeansList(logger=context.log, resource_config=context.resource_config)
