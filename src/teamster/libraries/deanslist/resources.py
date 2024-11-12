import yaml
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from requests import Session
from requests.exceptions import HTTPError


class DeansListResource(ConfigurableResource):
    subdomain: str
    api_key_map: str
    request_timeout: float = 60.0

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr()
    _api_key_map: dict = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)
        self._base_url = f"https://{self.subdomain}.deanslistsoftware.com/api"

        with open(self.api_key_map) as f:
            self._api_key_map = yaml.safe_load(f)["api_key_map"]

    def _get_url(self, api_version: str, endpoint: str, *args):
        if api_version == "beta":
            return (
                f"{self._base_url}/{api_version}/export/get-{endpoint}"
                f"{'-data' if endpoint in ['behavior', 'homework', 'comm'] else ''}"
                ".php"
            )
        elif args:
            return f"{self._base_url}/{api_version}/{endpoint}/{'/'.join(args)}"
        else:
            return f"{self._base_url}/{api_version}/{endpoint}"

    def _request(self, method: str, url: str, school_id: int, params: dict, **kwargs):
        self._log.info(f"GET:\t{url}\nSCHOOL_ID:\t{school_id}\nPARAMS:\t{params}")

        params["apikey"] = self._api_key_map[school_id]

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.request_timeout,
                **kwargs,
            )

            params.pop("apikey")

            response.raise_for_status()
            return response
        except HTTPError as e:
            params.pop("apikey")

            self._log.exception(e)
            raise e

    def get(
        self,
        api_version: str,
        endpoint: str,
        school_id: int,
        params: dict,
        *args,
        **kwargs,
    ):
        url = self._get_url(*args, api_version=api_version, endpoint=endpoint)

        response_json: dict = self._request(
            method="GET", url=url, school_id=school_id, params=params, **kwargs
        ).json()

        total_row_count = response_json.get("rowcount", 0) + response_json.get(
            "deleted_rowcount", 0
        )

        data = response_json.get("data", [])

        if isinstance(data, dict):
            data = [data]
            total_row_count = 1

        deleted_data = response_json.get("deleted_data", [])

        for d in deleted_data:
            d["is_deleted"] = True

        all_data = data + deleted_data

        return total_row_count, all_data

    def list(
        self,
        api_version: str,
        endpoint: str,
        school_id: int,
        params: dict,
        page_size: int = 250000,
        *args,
        **kwargs,
    ):
        page = 1
        total_pages = 2
        total_count = 0
        data = []

        url = self._get_url(*args, api_version=api_version, endpoint=endpoint)

        while page <= total_pages:
            params.update({"page_size": page_size, "page": page})

            response_json = self._request(
                method="GET", url=url, school_id=school_id, params=params, **kwargs
            ).json()

            data.extend(response_json["data"])

            total_count = response_json["total_count"]
            total_pages = response_json["total_pages"]
            page += 1

        return total_count, data
