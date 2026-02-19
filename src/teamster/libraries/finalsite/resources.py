import time
from datetime import datetime, timedelta

import jwt
from dagster import ConfigurableResource, DagsterLogManager
from dagster_shared import check
from pydantic import PrivateAttr
from requests import HTTPError, Response, Session


class FinalsiteResource(ConfigurableResource):
    server: str
    credential_id: str
    secret: str
    api_version: str = "1"

    _service_root: str = PrivateAttr(
        default="https://{0}.fsenrollment.com/api/external"
    )
    _session: Session = PrivateAttr(default_factory=Session)
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context):
        self._log = check.not_none(value=context.log)
        self._service_root = self._service_root.format(self.server)

        payload = {
            "sub": self.credential_id,
            "name": "Dagster",
            "exp": datetime.now() + timedelta(minutes=15),
        }

        token = jwt.encode(payload=payload, key=self.secret)

        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["X-Api-Version"] = self.api_version

    def _get_url(self, path: str, id: str | None) -> str:
        return f"{self._service_root}/{path}" + (f"/{id}" if id else "")

    def _request(self, method: str, path: str, id: str | None, **kwargs) -> Response:
        url = self._get_url(path=path, id=id)

        self._log.debug(msg=f"{method} {url}\n{kwargs}")
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            if response.status_code == 429:
                self._log.warning(response.text)
                retry_after = float(response.headers["Retry-After"])

                self._log.warning(f"Retrying request in {retry_after} second(s)...")
                time.sleep(retry_after)

                return self._request(method=method, path=path, id=id, **kwargs)
            else:
                self._log.error(response.text)
                raise e

    def get(self, path: str, id: str | None = None, **kwargs):
        return self._request(method="GET", path=path, id=id, **kwargs)

    def list(self, path, **kwargs):
        params = kwargs.get("params", {})

        all_data = []

        while True:
            response_json = self.get(path=path, params=params).json()

            next_cursor = response_json.get("meta", {}).get("next_cursor")
            all_data.extend(response_json[path])

            if next_cursor:
                params["cursor"] = next_cursor
            else:
                break

        return all_data
