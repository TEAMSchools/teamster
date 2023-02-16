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
            return f"{self.base_url}/{endpoint}"
        elif args is not None:
            return f"{self.base_url}/{self.api_version}/{endpoint}{'/'.join(args)}"
        else:
            return f"{self.base_url}/{self.api_version}/{endpoint}"

    def get_endpoint(self, endpoint, school_id, *args, **kwargs):
        url = self._get_url(endpoint, args)

        self.log.info(f"GET: {url}\nPARAMS: {kwargs}")

        params = kwargs.update(apikey=self.api_key_map[school_id])
        response = self.get(url=url, params=params)

        return response.json()


@resource(
    config_schema={
        "subdomain": StringSource,
        "api_key_map": Map({Int: StringSource}),
        "api_version": Field(
            config=StringSource, default_value="v1", is_required=False
        ),
    }
)
def deanslist_resource(context: InitResourceContext):
    return DeansList(logger=context.log, resource_config=context.resource_config)
