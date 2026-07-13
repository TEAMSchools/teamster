import pathlib

import fastavro
import fastavro.types
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Session
from requests.exceptions import HTTPError


def load_deanslist_config(
    key_dir: pathlib.Path,
) -> tuple[str, dict[int, str]]:
    subdomain = (key_dir / "subdomain").read_text().strip()

    api_key_map = {
        int(f.name): f.read_text().strip()
        for f in key_dir.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name.isdigit()
    }

    return subdomain, api_key_map


class DeansListResource(ConfigurableResource):
    api_key_dir: str
    request_timeout: float = 60.0

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr()
    _api_key_map: dict[int, str] = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)

        subdomain, self._api_key_map = load_deanslist_config(
            pathlib.Path(self.api_key_dir)
        )

        self._base_url = f"https://{subdomain}.deanslistsoftware.com/api"

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

        api_key = self._api_key_map.get(school_id)

        if api_key is None:
            raise KeyError(
                f"No DeansList API key for school_id {school_id} in "
                f"{self.api_key_dir}: add a field labeled '{school_id}' to the "
                "district's DeansList 1Password item, then re-sync the secret."
            )

        params["apikey"] = api_key

        response = self._session.request(
            method=method,
            url=url,
            params=params,
            timeout=self.request_timeout,
            **kwargs,
        )

        try:
            response.raise_for_status()
        except HTTPError as e:
            self._log.exception(e)
            raise e

        params.pop("apikey")
        return response

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
        avro_schema: fastavro.types.Schema | None = None,
        *args,
        **kwargs,
    ):
        page: int = 1
        total_pages: int = 2
        total_count: int = 0
        all_data: list[dict] = []

        data_filepath = pathlib.Path(
            f"env/deanslist/{endpoint}/{params['UpdatedSince']}/{school_id}/data.avro"
        ).absolute()

        url = self._get_url(*args, api_version=api_version, endpoint=endpoint)

        if avro_schema is not None:
            data_filepath.parent.mkdir(parents=True, exist_ok=True)

            with data_filepath.open("wb") as fo:
                fastavro.writer(
                    fo=fo,
                    schema=avro_schema,
                    records=[],
                    codec="snappy",
                    strict_allow_default=True,
                )

        fo = data_filepath.open("a+b")

        while page <= total_pages:
            params.update({"page_size": page_size, "page": page})

            response_json = self._request(
                method="GET", url=url, school_id=school_id, params=params, **kwargs
            ).json()

            total_count = response_json["total_count"]
            total_pages = response_json["total_pages"]
            data = response_json["data"]

            if avro_schema is not None:
                fastavro.writer(
                    fo=fo,
                    schema=avro_schema,
                    records=data,
                    codec="snappy",
                    strict_allow_default=True,
                )
            else:
                all_data.extend(data)

            page += 1

        fo.close()

        if avro_schema is not None:
            return int(total_count), data_filepath
        else:
            return int(total_count), all_data
