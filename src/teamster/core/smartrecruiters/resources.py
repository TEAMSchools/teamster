from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class SmartRecruitersResource(ConfigurableResource):
    smart_token: str

    _client: Session = PrivateAttr()
    _base_url: str = PrivateAttr(default="https://api.smartrecruiters.com")

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client = Session()
        self._client.headers["X-SmartToken"] = self.smart_token

        return super().setup_for_execution(context)

    def request(self, method, endpoint, **kwargs):
        try:
            response = self._client.request(
                method=method, url=f"{self._base_url}/{endpoint}", **kwargs
            )

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            context = self.get_resource_context()
            context.log.error(e)

            raise exceptions.HTTPError(response.text) from e
