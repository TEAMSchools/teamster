import time

from dagster import ConfigurableResource, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import HTTPError, Response, Session
from requests.auth import HTTPBasicAuth


class ZendeskResource(ConfigurableResource):
    subdomain: str
    email: str
    token: str
    page_size: int = 100
    api_version: str = "v2"

    _service_root: str = PrivateAttr(default="https://{0}.zendesk.com/api")
    _session: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._service_root = self._service_root.format(self.subdomain)
        self._session.headers = {"Content-Type": "application/json"}
        self._session.auth = HTTPBasicAuth(
            username=f"{self.email}/token", password=self.token
        )

    def _get_url(self, *args) -> str:
        return f"{self._service_root}/{self.api_version}/" + "/".join(
            str(a) for a in args if a
        )

    def _request(self, method: str, *args, **kwargs) -> Response:
        url = self._get_url(*args)
        params = kwargs.pop("params", {})

        self._log.debug(msg=f"{method}\t{url}\n{kwargs}")
        response = self._session.request(
            method=method, url=url, params=params, **kwargs
        )

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise e

    def get(self, resource: str, id: str | int | None = None, **kwargs) -> Response:
        return self._request("GET", resource, id, **kwargs)

    def put(
        self,
        resource: str,
        id: str | int | None = None,
        json: dict | None = None,
        **kwargs,
    ) -> Response:
        if json is None:
            json = {}

        return self._request("PUT", resource, id, json=json, **kwargs)

    def post(self, resource: str, json: dict | None = None, **kwargs) -> Response:
        if json is None:
            json = {}

        return self._request("POST", resource, json=json, **kwargs)

    def delete(self, resource: str, id: str | int | None = None, **kwargs) -> Response:
        return self._request("DELETE", resource, id, **kwargs)

    def list(self, resource: str, **kwargs) -> list[dict]:
        params = {"page[size]": self.page_size} | kwargs.get("params", {})

        all_data = []

        while True:
            data = self.get(resource=resource, params=params).json()

            if data["meta"]["has_more"]:
                all_data.extend(data[resource])
                params["page[after]"] = data["meta"]["after_cursor"]
            else:
                return all_data

    def handle_limit_exceeded(self, limit_header_reset_time: float) -> bool:
        wait_time = limit_header_reset_time - time.time() + 1  # Add 1 second buffer

        print(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
        time.sleep(wait_time)

        return False

    def handle_rate_limits(self, response: Response) -> bool:
        rate_limit_remaining = response.headers.get("ratelimit-remaining")

        if not rate_limit_remaining:
            return False

        if int(rate_limit_remaining) <= 0:
            return self.handle_limit_exceeded(
                float(response.headers.get("ratelimit-reset", "60"))
            )

        rate_limit_endpoint: str = response.headers.get(
            "Zendesk-RateLimit-Endpoint", ""
        )

        if not rate_limit_endpoint:
            return True

        parts = rate_limit_endpoint.split(";")

        if int(parts[1].split("=")[1]) > 0:
            return True

        return self.handle_limit_exceeded(int(parts[2].split("=")[1]))
