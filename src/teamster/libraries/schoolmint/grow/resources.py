import copy
import gc

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

    def _request(self, method, url, **kwargs):
        response = Response()

        try:
            response = self._session.request(method=method, url=url, **kwargs)

            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise HTTPError() from e

    def get(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint, *args)
        params = copy.deepcopy(self._default_params)

        params.update(kwargs)
        self._log.debug(f"GET: {url}\nPARAMS: {params}")

        if args:
            response = self._request(method="GET", url=url, params=params)

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

                self._log.debug(params)

            all_data["count"] = count

            return all_data

    def post(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint, *args)

        self._log.debug(f"POST: {url}")
        return self._request(method="POST", url=url, **kwargs).json()

    def put(self, endpoint, *args, **kwargs):
        url = self._get_url(endpoint, *args)

        self._log.debug(f"PUT: {url}")
        return self._request(method="PUT", url=url, **kwargs).json()

    def delete(self, endpoint, *args):
        url = self._get_url(endpoint, *args)

        self._log.debug(f"DELETE: {url}")
        return self._request(method="DELETE", url=url).json()
