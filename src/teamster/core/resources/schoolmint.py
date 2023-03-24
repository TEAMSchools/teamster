from dagster import Field, InitResourceContext, IntSource, StringSource, resource
from oauthlib.oauth2 import BackendApplicationClient
from requests import Session
from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session


class Grow(Session):
    def __init__(
        self,
        logger: InitResourceContext.log,
        resource_config: InitResourceContext.resource_config,
    ):
        self.log = logger

        self.base_url = "https://api.whetstoneeducation.com"
        self.api_response_limit = resource_config["api_response_limit"]

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

    def _request(self, method, path, params={}, body=None):
        try:
            response = self.request(
                method=method,
                url=f"{self.base_url}/external/{path}",
                params=params,
                json=body,
            )

            response.raise_for_status()
            return response
        except HTTPError as xc:
            if response.status_code >= 500:
                raise xc
            else:
                return response

    def get(self, schema, record_id=None, params={}):
        default_params = {"limit": self.api_response_limit, "skip": 0}
        default_params.update(params)

        if record_id:
            response = self._request(
                method="GET", path=f"{schema}/{record_id}", params=params
            )

            if response.ok:
                # mock standardized response format
                return {
                    "count": 1,
                    "limit": self.api_response_limit,
                    "skip": 0,
                    "data": [response.json()],
                }
            else:
                raise HTTPError(response.json())
        else:
            all_data = []

            while True:
                response = self._request(
                    method="GET", path=schema, params=default_params
                )

                if response.ok:
                    response_json = response.json()

                    data = response_json.get("data")

                    all_data.extend(data)
                    if len(all_data) >= response_json.get("count"):
                        break
                    else:
                        default_params["skip"] += default_params["limit"]
                else:
                    raise HTTPError(response.json())

            response_json.update({"data": all_data})
            return response_json

    def post(self, schema, params={}, body=None):
        response = self._request(method="POST", path=schema, params=params, body=body)

        if response.ok:
            return response.json()
        else:
            raise HTTPError(response.json())

    def put(self, schema, record_id, params={}, body=None):
        response = self._request(
            method="PUT", path=f"{schema}/{record_id}", params=params, body=body
        )

        if response.ok:
            return response.json()
        else:
            raise HTTPError(response.json())

    def delete(self, schema, record_id):
        response = self._request(method="DELETE", path=f"{schema}/{record_id}")

        if response.ok:
            return response.json()
        else:
            raise HTTPError(response.json())


@resource(
    config_schema={
        "client_id": StringSource,
        "client_secret": StringSource,
        "api_response_limit": Field(
            config=IntSource, is_required=False, default_value=100
        ),
    }
)
def schoolmint_grow_resource(context: InitResourceContext):
    return Grow(logger=context.log, resource_config=context.resource_config)
