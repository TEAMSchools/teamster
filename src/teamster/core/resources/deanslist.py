from dagster import Field, InitResourceContext, Int, Map, StringSource, resource
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
        self.api_version = resource_config["api_version"]
        self.api_key_map = resource_config["api_key_map"]
        self.base_url = f"https://{self.subdomain}.deanslistsoftware.com/api"

    def _get_url(self, endpoint, *args):
        if endpoint in ["behavior", "users"]:
            return (
                f"{self.base_url}/beta/export/get-{endpoint}"
                f"{'-data' if endpoint == 'behavior' else ''}"
                ".php"
            )
        elif args:
            return f"{self.base_url}/{self.api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self.base_url}/{self.api_version}/{endpoint}"

    def _parse_response_json(self, response_json):
        row_count = response_json.get("rowcount")
        deleted_row_count = response_json.get("deleted_rowcount", 0)

        if row_count is not None:
            total_row_count = row_count + deleted_row_count
        else:
            total_row_count = None

        data = response_json.get("data") or response_json
        deleted_data = response_json.get("deleted_data", [])
        for d in deleted_data:
            d["is_deleted"] = 1

        all_data = data + deleted_data

        return total_row_count, all_data

    def _get_url_json(self, url, params):
        response = self.get(url=url, params=params)
        response.raise_for_status()

        total_row_count, all_data = self._parse_response_json(response.json())

        return total_row_count, all_data

    def get_endpoint(self, endpoint, school_id, *args, **kwargs):
        url = self._get_url(endpoint, *args)

        self.log.info(f"GET: {url}\nPARAMS: {kwargs}")

        kwargs["apikey"] = self.api_key_map[school_id]

        total_row_count, all_data = self._get_url_json(url=url, params=kwargs)

        return total_row_count, all_data


@resource(
    config_schema={
        "subdomain": StringSource,
        "api_key_map": Map(key_type=Int, inner_type=StringSource),
        "api_version": Field(
            config=StringSource, default_value="v1", is_required=False
        ),
    }
)
def deanslist_resource(context: InitResourceContext):
    return DeansList(logger=context.log, resource_config=context.resource_config)
