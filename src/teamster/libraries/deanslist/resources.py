import pathlib
from typing import Any

import fastavro
import fastavro.types
import yaml
from pydantic import PrivateAttr
from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class DeansListResource(BaseHTTPResource):
    subdomain: str
    api_key_map: str

    _api_key_map: dict = PrivateAttr()
    _current_school_id: int = PrivateAttr(default=0)

    def _setup_session(self) -> None:
        self._base_url = f"https://{self.subdomain}.deanslistsoftware.com/api"

        with open(self.api_key_map) as f:
            self._api_key_map = yaml.safe_load(f)["api_key_map"]

    def _get_url(self, *parts: str) -> str:
        """DeansList URL construction.

        Args:
            *parts: (api_version, endpoint, *extra_parts).
                Beta endpoints use PHP export format with -data suffix for
                behavior, homework, comm.
        """
        if len(parts) < 2:
            return self._base_url + "/" + "/".join(parts)

        api_version, endpoint, *extra = parts

        if api_version == "beta":
            suffix = "-data" if endpoint in ("behavior", "homework", "comm") else ""
            return f"{self._base_url}/{api_version}/export/get-{endpoint}{suffix}.php"

        if extra:
            return f"{self._base_url}/{api_version}/{endpoint}/{'/'.join(extra)}"
        return f"{self._base_url}/{api_version}/{endpoint}"

    def _prepare_request(
        self, method: str, url: str, kwargs: dict
    ) -> tuple[str, str, dict]:
        """Inject school-specific API key into params."""
        if self._current_school_id:
            params = kwargs.setdefault("params", {})
            params["apikey"] = self._api_key_map[self._current_school_id]
        return method, url, kwargs

    def _post_request(self, kwargs: dict) -> None:
        """Strip apikey from params after request to avoid logging it."""
        params = kwargs.get("params", {})
        params.pop("apikey", None)

    # trunk-ignore(pyright/reportIncompatibleMethodOverride): DeansList API returns tuple, not Response
    def get(
        self,
        api_version: str,
        endpoint: str,
        school_id: int,
        params: dict,
        *args: str,
        **kwargs,
    ) -> tuple[int, list[dict[str, Any]]]:
        self._current_school_id = school_id
        self._log.info(
            f"GET:\t{self._get_url(api_version, endpoint, *args)}"
            f"\nSCHOOL_ID:\t{school_id}\nPARAMS:\t{params}"
        )

        url = self._get_url(api_version, endpoint, *args)
        response = self._request_with_cleanup("GET", url, params=params, **kwargs)
        response_json: dict = response.json()

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
        self._current_school_id = 0
        return total_row_count, all_data

    def list(
        self,
        api_version: str,
        endpoint: str,
        school_id: int,
        params: dict,
        page_size: int = 250000,
        avro_schema: fastavro.types.Schema | None = None,
        *args: str,
        **kwargs,
    ) -> tuple[int, list[dict[str, Any]] | pathlib.Path]:
        self._current_school_id = school_id

        data_filepath = pathlib.Path(
            f"env/deanslist/{endpoint}/{params['UpdatedSince']}/{school_id}/data.avro"
        ).absolute()

        url = self._get_url(api_version, endpoint, *args)

        all_data: list[dict[str, Any]] = []
        total_count = 0

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

        fo = data_filepath.open("a+b") if avro_schema is not None else None

        def fetch_page(page_params: dict) -> Response:
            merged = {**params, **page_params}
            return self._request_with_cleanup("GET", url, params=merged, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            nonlocal total_count
            response_json = resp.json()
            total_count = response_json["total_count"]
            return response_json["data"]

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=page_size,
            page_param="page",
            size_param="page_size",
        ):
            if avro_schema is not None and fo is not None:
                fastavro.writer(
                    fo=fo,
                    schema=avro_schema,
                    records=page_records,
                    codec="snappy",
                    strict_allow_default=True,
                )
            else:
                all_data.extend(page_records)

        if fo is not None:
            fo.close()

        self._current_school_id = 0

        if avro_schema is not None:
            return int(total_count), data_filepath
        return int(total_count), all_data

    def _request_with_cleanup(self, method: str, url: str, **kwargs) -> Response:
        """Call _request then strip apikey from params."""
        response = super()._request(method, url, **kwargs)
        self._post_request(kwargs)
        return response
