import copy

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session


class SchoolMintGrowResource(ConfigurableResource):
    client_id: str
    client_secret: str
    district_id: str
    api_response_limit: int = 100

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="https://grow-api.schoolmint.com")
    _default_params: dict = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

        self._default_params = {
            "limit": self.api_response_limit,
            "district": self.district_id,
            "skip": 0,
        }

        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._get_access_token()["access_token"],
            }
        )

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

    def _request(self, method, url, **kwargs) -> Response:
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise HTTPError(response.text) from e

    def get(self, endpoint, *args, **kwargs) -> dict:
        url = self._get_url(endpoint, *args)
        params = copy.deepcopy(self._default_params)

        params.update(kwargs)

        if args:
            self._log.debug(f"GET: {url}\nPARAMS: {params}")
            response_json = self._request(method="GET", url=url, params=params).json()

            # mock paginated response format
            return {
                "count": 1,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": [response_json],
            }
        else:
            data = []

            response = {
                "count": 0,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": data,
            }

            while True:
                self._log.debug(f"GET: {url}\nPARAMS: {params}")
                response_json = self._request(
                    method="GET", url=url, params=params
                ).json()

                count = response_json["count"]
                data.extend(response_json.get("data", []))

                len_data = len(data)

                if len_data >= count:
                    break
                else:
                    params["skip"] += params["limit"]

            response["count"] = count

            if len_data != count:
                raise Exception("API returned an incomplete response")
            else:
                return response

    def post(self, endpoint, *args, **kwargs) -> dict:
        url = self._get_url(endpoint, *args)

        self._log.debug(f"POST: {url}")
        return self._request(method="POST", url=url, **kwargs).json()

    def put(self, endpoint, *args, **kwargs) -> dict:
        url = self._get_url(endpoint, *args)

        self._log.debug(f"PUT: {url}")
        return self._request(method="PUT", url=url, **kwargs).json()

    def delete(self, endpoint, *args):
        url = self._get_url(endpoint, *args)

        self._log.debug(f"DELETE: {url}")
        return self._request(method="DELETE", url=url).json()
