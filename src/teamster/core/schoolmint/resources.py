import copy
import gc

from dagster import ConfigurableResource, InitResourceContext
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Session
from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session


class SchoolMintGrowResource(ConfigurableResource):
    client_id: str
    client_secret: str
    district_id: str
    api_response_limit: int = 100

    _client: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="https://api.whetstoneeducation.com")
    _default_params: dict = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._default_params = {
            "limit": self.api_response_limit,
            "district": self.district_id,
            "skip": 0,
        }

        access_token = self._get_access_token(
            client_id=self.client_id, client_secret=self.client_secret
        )

        self._client.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer " + access_token.get("access_token"),
            }
        )

        return super().setup_for_execution(context)

    def _get_access_token(self):
        oauth = OAuth2Session(client=BackendApplicationClient(client_id=self.client_id))

        return oauth.fetch_token(
            token_url=f"{self._base_url}/auth/client/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

    def _get_url(self, endpoint, *args):
        return f"{self._base_url}/external/{endpoint}" + (
            "/" + "/".join(args) if args else ""
        )

    def _request(self, method, url, params={}, body=None):
        context = self.get_resource_context()

        context.log.debug(f"{method}: {url}\nPARAMS: {params}")

        try:
            response = self._client.request(
                method=method, url=url, params=params, json=body
            )

            response.raise_for_status()
            return response
        except HTTPError as e:
            if response.status_code >= 500:
                raise HTTPError from e
            else:
                raise HTTPError(response.json()) from e

    def get(self, endpoint, *args, **kwargs):
        context = self.get_resource_context()

        url = self._get_url(endpoint=endpoint, *args)

        params = copy.deepcopy(self._default_params)
        params.update(kwargs)

        if args:
            response = self._request(method="GET", url=url, params=kwargs)

            # mock paginated response format
            return {
                "count": 1,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": [response.json()],
            }
        else:
            all_data = {
                "count": 0,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": [],
            }

            while True:
                response = self._request(method="GET", url=url, params=params)

                response_json = response.json()
                del response
                gc.collect()

                count = response_json.get("count", 0)
                data = response_json.get("data", [])
                del response_json
                gc.collect()

                all_data["data"].extend(data)
                del data
                gc.collect()

                if len(all_data["data"]) >= count:
                    break
                else:
                    params["skip"] += params["limit"]

            all_data["count"] = count

            context.log.debug(f"COUNT: {count}")
            return all_data

    def post(self, endpoint, body=None, **kwargs):
        return self._request(
            method="POST",
            url=self._get_url(endpoint=endpoint),
            params=kwargs,
            body=body,
        ).json()

    def put(self, endpoint, body=None, *args, **kwargs):
        return self._request(
            method="PUT",
            url=self._get_url(endpoint=endpoint, *args),
            params=kwargs,
            body=body,
        ).json()

    def delete(self, endpoint, *args):
        return self._request(
            method="DELETE", url=self._get_url(endpoint=endpoint, *args)
        ).json()
