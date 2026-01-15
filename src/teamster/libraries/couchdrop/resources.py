import pathlib

from dagster import ConfigurableResource, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import HTTPError, Response, Session


class CouchdropResource(ConfigurableResource):
    username: str
    password: str

    _service_root: str = PrivateAttr()
    _session: Session = PrivateAttr(default_factory=Session)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._service_root = "https://api.couchdrop.io"

        authenticate_json = self.post(
            resource="authenticate",
            data={"username": self.username, "password": self.password},
        ).json()

        self._session.headers["token"] = authenticate_json["token"]
        self._service_root = "https://fileio.couchdrop.io"

    def _get_url(self, *args) -> str:
        return f"{self._service_root}/" + "/".join(str(a) for a in args if a)

    def _request(self, method: str, *args, **kwargs) -> Response:
        url = self._get_url(*args)

        self._log.debug(msg=f"{method} {url}\n{kwargs}")
        response = self._session.request(method=method, url=url, **kwargs)

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._log.error(response.text)
            raise e

    def get(self, resource: str, id: str | int | None = None, **kwargs):
        return self._request("GET", resource, id, **kwargs)

    def put(
        self,
        resource: str,
        id: str | int | None = None,
        data: dict | None = None,
        **kwargs,
    ):
        if data is None:
            data = {}

        return self._request("PUT", resource, id, data=data, **kwargs)

    def post(self, resource: str, data: dict | None = None, **kwargs):
        if data is None:
            data = {}

        return self._request("POST", resource, data=data, **kwargs)

    def delete(self, resource: str, id: str | int | None = None, **kwargs):
        return self._request("DELETE", resource, id, **kwargs)

    def ls_r(
        self,
        path: str = "/",
        exclude_dirs: list[str] | None = None,
        files: list | None = None,
    ) -> list:
        if exclude_dirs is None:
            exclude_dirs = []

        if files is None:
            files = []

        if path in exclude_dirs:
            return files

        self._log.info(f"Listing of all files under {path}")
        ls_response = self.post(resource="file/ls", data={"path": path})

        for file in ls_response.json().get("ls", []):
            sub_path = str(pathlib.Path(path) / file["filename"])

            if file["is_dir"]:
                self.ls_r(path=sub_path, exclude_dirs=exclude_dirs, files=files)
            else:
                files.append((file, sub_path))

        return files
