from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr
from requests import Session, exceptions


class SmartRecruitersResource(ConfigurableResource):
    smart_token: str

    _client: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="https://api.smartrecruiters.com")

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client.headers["X-SmartToken"] = self.smart_token

    def _get_url(self, endpoint, *args):
        return f"{self._base_url}/{endpoint}" + ("/" + "/".join(args) if args else "")

    def _request(self, method, url, **kwargs):
        try:
            response = self._client.request(method=method, url=url, **kwargs)

            response.raise_for_status()

            return response
        except exceptions.HTTPError as e:
            context = self.get_resource_context()

            context.log.error(e)

            raise exceptions.HTTPError(response.text) from e

    def get(self, endpoint, *args, **kwargs):
        context = self.get_resource_context()

        url = self._get_url(endpoint=endpoint, *args)
        context.log.debug(f"GET: {url}")

        return self._request(method="GET", url=url, **kwargs)

    def post(self, endpoint, *args, **kwargs):
        context = self.get_resource_context()

        url = self._get_url(endpoint=endpoint, *args)
        context.log.debug(f"POST: {url}")

        return self._request(
            method="POST", url=self._get_url(endpoint=endpoint, *args), **kwargs
        )
