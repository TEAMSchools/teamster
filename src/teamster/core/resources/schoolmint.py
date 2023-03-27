import copy

from dagster import Field, InitResourceContext, IntSource, StringSource, resource
from oauthlib.oauth2 import BackendApplicationClient
from requests import Session
from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session


class Grow(Session):
    def __init__(self, logger, resource_config: InitResourceContext.resource_config):
        super().__init__()

        self.log: InitResourceContext.log = logger

        self.base_url = "https://api.whetstoneeducation.com"
        self.default_params = {
            "limit": resource_config["api_response_limit"],
            "district": resource_config["district_id"],
            "skip": 0,
        }

        self.access_token = self._get_access_token(
            client_id=resource_config["client_id"],
            client_secret=resource_config["client_secret"],
        )

        self.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token.get('access_token')}",
            }
        )

    def _get_access_token(self, client_id, client_secret):
        client = BackendApplicationClient(client_id=client_id)

        oauth = OAuth2Session(client=client)

        return oauth.fetch_token(
            token_url=f"{self.base_url}/auth/client/token",
            client_id=client_id,
            client_secret=client_secret,
        )

    def _get_url(self, endpoint, *args):
        return f"{self.base_url}/external/{endpoint}" + (
            "/" + "/".join(args) if args else ""
        )

    def _request(self, method, url, params={}, body=None):
        self.log.debug(f"{method}: {url}")
        self.log.debug(f"PARAMS: {params}")

        try:
            response = self.request(method=method, url=url, params=params, json=body)

            response.raise_for_status()
            return response
        except HTTPError as e:
            if response.status_code >= 500:
                raise HTTPError from e
            else:
                raise HTTPError(response.json()) from e

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint=endpoint, *args)

        params = copy.deepcopy(self.default_params)
        params.update(kwargs)

        if args:
            response = self._request(method="GET", url=url, params=kwargs)

            # mock standardized response format
            return {
                "count": 1,
                "limit": self.api_response_limit,
                "skip": 0,
                "data": [response.json()],
            }
        else:
            all_data = []
            while True:
                response = self._request(method="GET", url=url, params=params)

                response_json = response.json()

                all_data.extend(response_json["data"])
                if len(all_data) >= response_json["count"]:
                    break
                else:
                    params["skip"] += params["limit"]

            self.log.debug(f"COUNT: {response_json['count']}")

            response_json.update({"data": all_data})
            return response_json

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


@resource(
    config_schema={
        "client_id": StringSource,
        "client_secret": StringSource,
        "district_id": StringSource,
        "api_response_limit": Field(
            config=IntSource, is_required=False, default_value=100
        ),
    }
)
def schoolmint_grow_resource(context: InitResourceContext):
    return Grow(logger=context.log, resource_config=context.resource_config)
